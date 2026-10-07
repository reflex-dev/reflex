#!/usr/bin/env bash
# Blank-app smoke: reflex init --template blank, then dev and prod runs driven in Chromium.
# usage: smoke.sh <venv> <workdir> <port-base> <logdir>   (dev: fp=base, bp=base+5000; prod: single port base+1)
set -u
V="$1"; WD="$2"; B="$3"; L="$4"; mkdir -p "$WD" "$L"; cd "$WD"
export REFLEX_TELEMETRY_ENABLED=false
DRV="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 ${SB:?}/envs/driver/bin/python /home/user/reflex/.claude/skills/prerelease-test/scripts/drive_app.py"
[ -f rxconfig.py ] || "$V/bin/reflex" init --template blank > "$L/init.log" 2>&1 || { echo "init failed"; tail -20 "$L/init.log"; exit 1; }
wait_up() { for i in $(seq 1 180); do curl -s --noproxy '*' -o /dev/null -w '%{http_code}' "$1" | grep -q 200 && return 0; sleep 2; done; return 1; }
stop() { kill -TERM -- -"$1" 2>/dev/null; for i in $(seq 1 30); do kill -0 "$1" 2>/dev/null || return 0; sleep 1; done; kill -KILL -- -"$1" 2>/dev/null; }
fp=$B; bp=$((B+5000))
setsid "$V/bin/reflex" run --frontend-port $fp --backend-port $bp > "$L/dev.log" 2>&1 & pid=$!
if wait_up "http://localhost:$fp/"; then sleep 3; $DRV "http://localhost:$fp/" --report "$L/dev.json" --screenshot "$L/dev.png"; echo "dev drive exit=$?"; else echo "dev never came up"; fi
stop $pid
pp=$((B+1))
setsid env REFLEX_API_URL=http://localhost:$pp "$V/bin/reflex" run --env prod --frontend-port $pp --backend-port $pp > "$L/prod.log" 2>&1 & pid=$!
if wait_up "http://localhost:$pp/"; then sleep 3; $DRV "http://localhost:$pp/" --report "$L/prod.json" --screenshot "$L/prod.png"; echo "prod drive exit=$?"; else echo "prod never came up"; fi
stop $pid
grep -iE 'error|traceback|warn' "$L/dev.log" "$L/prod.log" | grep -v 'npmmirror' | head -20
