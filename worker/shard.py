#!/usr/bin/env python3
"""One shard of an encrypted sim batch (a GitHub Actions job, or the PC's dry run): decrypt, keep every chunk whose
tid % count == index, run them through worker.py, encrypt the answers. Plain text only passes through pipes and
worker.py's temp profiles.
usage: shard.py <batch.enc> <index> <count> <out.enc>     env: SIM_KEY (passphrase), SIMC (default ~/simc-bin/simc)"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OPENSSL = ["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-iter", "200000", "-md", "sha256", "-pass", "env:SIM_KEY"]
batch, index, count, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]


def openssl(args, data=None):
    p = subprocess.run(OPENSSL + args, input=data, capture_output=True)
    if p.returncode:
        sys.exit(f"openssl: {p.stderr.decode(errors='replace').strip()}")
    return p.stdout


mine, n = [], 0
for line in openssl(["-d", "-in", batch]).decode().splitlines():
    msg = json.loads(line)
    if msg["op"] == "profile":
        mine.append(line)
    elif msg["tid"] % count == index:
        mine.append(line)
        n += 1
simc = os.environ.get("SIMC") or os.path.expanduser("~/simc-bin/simc")
answers = subprocess.run([sys.executable, os.path.join(HERE, "worker.py"), "--simc", simc],
                         input="\n".join(mine) + "\n", stdout=subprocess.PIPE, text=True).stdout
os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
openssl(["-salt", "-out", out], answers.encode())
print(f"shard {index + 1}/{count}: {n} chunks")
