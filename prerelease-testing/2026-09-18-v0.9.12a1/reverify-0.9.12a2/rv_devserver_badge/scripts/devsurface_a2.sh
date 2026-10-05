#!/bin/bash
# Dev-server surface on a2: JSON logs (#7193), held-open browser hot reload,
# syntax-error recovery, clean SIGINT to the process group, no leftover listener.
SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad
W=$SB/reverify/rv_devserver_badge
export REFLEX_TELEMETRY_ENABLED=false
nap() { python3 -c "import time,sys;time.sleep(float(sys.argv[1]))" "$1"; }
cd $W/apps/dsc_a2 || exit 1
setsid $SB/envs/a2/bin/reflex run --json --loglevel debug --frontend-port 3227 --backend-port 8227 > $W/logs/devsurface_a2.log 2>&1 &
PID=$!
echo "PID=$PID"
n=0; until curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:3227/ 2>/dev/null | grep -q '^200$'; do n=$((n+1)); [ $n -ge 360 ] && { echo "TIMEOUT"; break; }; nap 1; done; echo "frontend 200 after ${n}s"
nap 3
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python $W/scripts/hr_browser.py \
   http://localhost:3227/ http://localhost:8227 $W/apps/dsc_a2/dsc/dsc.py $W/shots $W/out/hr_a2.json
echo "hr exit=$?"
echo "== SIGINT to process group =="
T0=$(python3 -c "import time;print(time.time())")
kill -INT -$PID 2>/dev/null
for i in $(seq 1 30); do kill -0 $PID 2>/dev/null || break; nap 1; done
wait $PID; EC=$?
T1=$(python3 -c "import time;print(time.time())")
echo "exit_code=$EC after $(python3 -c "print(round($T1-$T0,2))")s"
nap 2
echo "== ports after SIGINT =="; cd $SB && uv run --no-project python $SB/bin/ports.py 3227 8227 2>&1 | grep -v UV_NATIVE; echo "(empty=free)"
echo "DEVSURFACE DONE"
