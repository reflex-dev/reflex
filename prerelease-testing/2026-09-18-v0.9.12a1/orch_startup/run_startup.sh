#!/bin/bash
# #7049 relative baseline: backend-only startup time to /ping, worker RSS, import-time module set — 0.9.11.post1 vs 0.9.12a1.
SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad
P=$SB/apps/orch_startup; DEST=/home/user/reflex/prerelease-testing/2026-09-18-v0.9.12a1
export REFLEX_TELEMETRY_ENABLED=false
run_case() { # tag venv appdir port
  local tag=$1 V=$2 A=$3 BP=$4
  rm -rf $P/$tag && cp -r $A $P/$tag && rm -rf $P/$tag/.web $P/$tag/.states $P/$tag/reflex.lock
  echo "=== $tag: $($V/bin/python -c 'import reflex; print(reflex.constants.Reflex.VERSION)')"
  $V/bin/python - <<'PY' 2>&1 | sed "s/^/[$tag] /"
import sys, time
t=time.perf_counter(); import reflex; dt=time.perf_counter()-t
heavy=[m for m in ("sqlalchemy","sqlmodel","alembic","pandas","PIL","plotly","httpx","starlette_admin","reflex.compiler","reflex.compiler.compiler","reflex.istate.manager","redis") if m in sys.modules]
print(f"import reflex: {dt*1e3:.0f} ms, {len(sys.modules)} modules; heavy present: {heavy}")
PY
  for i in 1 2 3; do
    cd $P/$tag; local t0=$(date +%s.%N)
    setsid $V/bin/reflex run --backend-only --backend-port $BP --loglevel warning > $P/logs/${tag}_run$i.log 2>&1 &
    local n=0; until curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:$BP/ping 2>/dev/null | grep -q '^200$'; do n=$((n+1)); [ $n -ge 1200 ] && break; sleep 0.1; done
    local t1=$(date +%s.%N); sleep 3
    local rss=$(ps -eo pid,rss,args | grep -E "reflex run --backend-only --backend-port $BP" | grep -v grep | awk '{s+=$2; c++} END{printf "%d MB over %d procs", s/1024, c}')
    echo "[$tag] run$i: time to /ping 200 = $(python3 -c "print(round($t1-$t0,2))") s; RSS (all reflex procs for this port) = $rss"
    for p in $(python3 $SB/bin/ports.py $BP | grep -oE 'pids=[0-9,]+' | cut -d= -f2 | tr ',' ' '); do pkill -KILL -P $p 2>/dev/null; kill -KILL $p 2>/dev/null; done
    for p in $(pgrep -f "reflex run --backend-only --backend-port $BP"); do kill -KILL $p 2>/dev/null; done; sleep 1
  done
  python3 $SB/bin/ports.py $BP >/dev/null && echo "[$tag] port free"
}
run_case prev $SB/envs/prev $DEST/dev_server_cli/dsc_prev 8056
run_case new  $SB/envs/shared $DEST/dev_server_cli/dsc 8057
echo "STARTUP DONE"
