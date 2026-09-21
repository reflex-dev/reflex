#!/bin/bash
# FINDING-012: vapp prod with the DEFAULT badge setting; probe the #portal + overlay.
# usage: vapp_prod.sh <venv> <appdir> <port> <label>
SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad
W=$SB/reverify/rv_devserver_badge
VENV=$1; APPDIR=$2; PORT=$3; LABEL=$4
export REFLEX_TELEMETRY_ENABLED=false
nap() { python3 -c "import time,sys;time.sleep(float(sys.argv[1]))" "$1"; }
cd $APPDIR || exit 1
setsid $VENV/bin/reflex run --env prod --frontend-port $PORT --backend-port $PORT --loglevel debug > $W/logs/vapp_${LABEL}.log 2>&1 &
PID=$!; echo "PID=$PID"
n=0; until curl -s --noproxy '*' -m 3 -o /dev/null -w '%{http_code}' http://localhost:$PORT/ 2>/dev/null | grep -q '^200$'; do n=$((n+1)); [ $n -ge 300 ] && { echo "TIMEOUT"; tail -20 $W/logs/vapp_${LABEL}.log; break; }; nap 1; done; echo "prod 200 after ${n}s"
nap 3
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python $W/scripts/editor_probe.py http://localhost:$PORT $LABEL $W/shots | tee $W/out/editor_${LABEL}.json
echo "probe exit=$?"
cp .web/build/client/../../../.web/app/root.jsx $W/out/root_${LABEL}.jsx 2>/dev/null || cp .web/app/root.jsx $W/out/root_${LABEL}.jsx 2>/dev/null
kill -TERM -$PID 2>/dev/null; nap 4; kill -KILL -$PID 2>/dev/null; nap 2
echo "== ports after =="; cd $SB && uv run --no-project python $SB/bin/ports.py $PORT 2>&1 | grep -v UV_NATIVE; echo "(empty=free)"
echo "VAPP $LABEL DONE"
