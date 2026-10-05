#!/bin/bash
SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad
W=$SB/reverify/rv_devserver_badge
export REFLEX_TELEMETRY_ENABLED=false
nap() { python3 -c "import time,sys;time.sleep(float(sys.argv[1]))" "$1"; }
cd $W/apps/dsc_a2 || exit 1
setsid $SB/envs/a2/bin/reflex run --frontend-port 3232 --backend-port 8232 > $W/logs/sigint_a2.log 2>&1 &
PID=$!; echo "PID=$PID"
n=0; until curl -s --noproxy '*' -m 3 -o /dev/null -w '%{http_code}' http://localhost:3232/ 2>/dev/null | grep -q '^200$'; do n=$((n+1)); [ $n -ge 240 ] && { echo "TIMEOUT"; break; }; nap 1; done; echo "frontend 200 after ${n}s"
curl -s --noproxy '*' -o /dev/null -w "backend /ping %{http_code}\n" http://localhost:8232/ping
T0=$(python3 -c "import time;print(time.time())")
kill -INT -$PID
for i in $(seq 1 30); do kill -0 $PID 2>/dev/null || break; nap 1; done
wait $PID; EC=$?
T1=$(python3 -c "import time;print(time.time())")
echo "exit_code=$EC after $(python3 -c "print(round($T1-$T0,2))")s"
nap 2
echo "ports_after:"; cd $SB && uv run --no-project python $SB/bin/ports.py 3232 8232 2>&1 | grep -v UV_NATIVE
echo "(empty above = no listener)"
echo "log tail:"; tail -4 $W/logs/sigint_a2.log
echo "SIGINT TEST DONE"
