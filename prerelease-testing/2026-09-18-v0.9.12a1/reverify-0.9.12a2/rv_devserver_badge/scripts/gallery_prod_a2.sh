#!/bin/bash
SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad
W=$SB/reverify/rv_devserver_badge
export REFLEX_TELEMETRY_ENABLED=false
nap() { python3 -c "import time,sys;time.sleep(float(sys.argv[1]))" "$1"; }
cd $W/apps/gallery || exit 1
setsid $W/venv/bin/reflex run --env prod --frontend-port 3231 --backend-port 3231 --loglevel debug > $W/logs/gallery_prod.log 2>&1 &
PID=$!; echo "PID=$PID"
n=0; until curl -s --noproxy '*' -m 3 -o /dev/null -w '%{http_code}' http://localhost:3231/ 2>/dev/null | grep -q '^200$'; do n=$((n+1)); [ $n -ge 400 ] && { echo "TIMEOUT"; tail -30 $W/logs/gallery_prod.log; break; }; nap 1; done; echo "prod 200 after ${n}s"
nap 3
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python $W/scripts/drive.py http://localhost:3231 $W/shots gprod 2>&1 | tail -70
echo "drive exit=$?"
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python $W/scripts/portal_probe.py http://localhost:3231 gprod 2>&1 | tail -30
kill -TERM -$PID 2>/dev/null; nap 4; kill -KILL -$PID 2>/dev/null; nap 2
echo "== ports after =="; cd $SB && uv run --no-project python $SB/bin/ports.py 3231 2>&1 | grep -v UV_NATIVE; echo "(empty=free)"
echo "GALLERY DONE"
