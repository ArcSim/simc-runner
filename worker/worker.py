#!/usr/bin/env python3
"""simc worker: runs single-thread simc chunks sent as JSON lines on stdin, answers with JSON lines on stdout.

Reached through any pipe: `ssh host python3 /opt/simcw/worker.py`, a local `python worker.py --simc <simc>`,
`docker run -i --rm simc-worker`, or shard.py. No network port, no dependencies.

in : {"op":"profile","pid":ID,"text":PROFILE}            sent once per profile, before its tasks
     {"op":"task","tid":N,"pid":ID,"seed":S,"iterations":I,"threads":T}
out: {"op":"hello","version":LINE,"slots":N,"host":NAME}  first line, before any input is read
     {"op":"done","tid":N,"dps":"<simc's own digits>","secs":X}
     {"op":"fail","tid":N,"error":TEXT}
EOF on stdin = finish the running tasks, then exit."""
import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor

ap = argparse.ArgumentParser()
ap.add_argument("--simc", default=os.environ.get("SIMC", "/opt/simc/build/simc"))
ap.add_argument("--slots", type=int, default=int(os.environ.get("SLOTS", "0")) or os.cpu_count())
ap.add_argument("--tmp", default=None)
args = ap.parse_args()

tmp = args.tmp or tempfile.mkdtemp(prefix="simcw_")
os.makedirs(tmp, exist_ok=True)
out_lock = threading.Lock()


def send(msg):
    with out_lock:
        sys.stdout.write(json.dumps(msg) + "\n")
        sys.stdout.flush()


def version():
    # Many workers starting at once on a loaded machine can miss the version line; ask again before giving up.
    for _ in range(3):
        p = subprocess.run([args.simc, "display_build=1"], capture_output=True, text=True)
        m = re.search(r"SimulationCraft .*", p.stdout)
        if m:
            return m.group(0).strip()
        time.sleep(1)
    return f"unknown (exit {p.returncode}: {(p.stdout + p.stderr).strip()[-120:]})"


# The DPS line keeps simc's own digits; the driver merges chunks from these exact strings.
DPS_RE = re.compile(r"^\s*DPS=([\d.]+)", re.M)


def run(task, path):
    try:
        attempt(task, path)
    except Exception as e:  # an exception inside the pool would vanish and leave the driver waiting
        send({"op": "fail", "tid": task["tid"], "error": repr(e)})


def attempt(task, path):
    t0 = time.time()
    cmd = [args.simc, path, f"iterations={task['iterations']}", f"threads={task['threads']}", "deterministic=1",
           f"seed={task['seed']}"]
    p = subprocess.run(cmd, capture_output=True, text=True)
    m = DPS_RE.search(p.stdout)
    if not m:
        tail = (p.stdout + p.stderr).strip().splitlines()[-5:]
        send({"op": "fail", "tid": task["tid"], "error": " | ".join(tail) or f"exit {p.returncode}"})
        return
    send({"op": "done", "tid": task["tid"], "dps": m.group(1), "secs": round(time.time() - t0, 2)})


send({"op": "hello", "version": version(), "slots": args.slots, "host": socket.gethostname(), "platform": sys.platform})
profiles = {}
with ThreadPoolExecutor(max_workers=args.slots) as pool:
    for line in sys.stdin:
        if not line.strip():
            continue
        msg = json.loads(line)
        if msg["op"] == "profile":
            path = os.path.join(tmp, f"{msg['pid']}.simc")
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(msg["text"])
            profiles[msg["pid"]] = path
        elif msg["op"] == "task":
            if msg["pid"] not in profiles:
                send({"op": "fail", "tid": msg["tid"], "error": f"unknown profile {msg['pid']}"})
                continue
            pool.submit(run, msg, profiles[msg["pid"]])
if not args.tmp:
    shutil.rmtree(tmp, ignore_errors=True)
