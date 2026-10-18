#!/usr/bin/env bash
# simc worker on Ubuntu 22.04/24.04 x86-64: stock simc at the Raidbots commit + worker.py + idle power-off.
# Run as root from the folder holding worker.py (cloud-init does this). About 10 min on 64 cores, mostly compiling.
# env: SIMC_COMMIT (Raidbots' build), IDLE_MIN (power off after this many idle minutes; 0 = never), NO_IDLE=1 (Docker)
set -euo pipefail
SIMC_COMMIT=${SIMC_COMMIT:-5537d8813dfc59707927722b1e23ffa6fd67ee59}
IDLE_MIN=${IDLE_MIN:-30}
HERE=$(cd "$(dirname "$0")" && pwd)

export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q --no-install-recommends build-essential cmake ninja-build git ca-certificates python3

mkdir -p /opt/simc
cd /opt/simc
[ -d .git ] || { git init -q; git remote add origin https://github.com/simulationcraft/simc.git; }
git fetch -q --depth 1 origin "$SIMC_COMMIT"
git checkout -q --force FETCH_HEAD
# No FMA contraction: x86-64 baseline has none anyway, this keeps it so if flags ever add -march.
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DBUILD_GUI=OFF -DBUILD_TESTING=OFF -DSC_NO_NETWORKING=ON \
      -DCMAKE_CXX_FLAGS="-ffp-contract=off"
ninja -C build simc
build/simc display_build=1 | tail -n 1

mkdir -p /opt/simcw
install -m 0755 "$HERE/worker.py" /opt/simcw/worker.py

if [ "${NO_IDLE:-0}" != "1" ] && [ "$IDLE_MIN" -gt 0 ]; then
  # A minute counts as idle when no worker, no simc and no login shell is running. /run is cleared at boot,
  # so a restarted machine starts from zero.
  cat > /usr/local/bin/simcw-idle <<EOF
#!/bin/sh
f=/run/simcw-idle
if pgrep -f simcw/worker.py >/dev/null || pgrep -x simc >/dev/null || who | grep -q pts; then echo 0 > \$f; exit 0; fi
n=\$(( \$(cat \$f 2>/dev/null || echo 0) + 1 )); echo \$n > \$f
[ \$n -ge $IDLE_MIN ] && /sbin/shutdown -h now
exit 0
EOF
  chmod 0755 /usr/local/bin/simcw-idle
  echo "* * * * * root /usr/local/bin/simcw-idle" > /etc/cron.d/simcw-idle
fi
echo "simc worker ready"
