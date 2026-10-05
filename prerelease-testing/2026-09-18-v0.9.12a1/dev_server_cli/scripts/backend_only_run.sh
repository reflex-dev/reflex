#!/bin/bash
# usage: backend_only_run.sh <venv> <appdir> <bp> <logfile> [extra args...]
VENV=$1; APPDIR=$2; BP=$3; LOG=$4; shift 4
cd "$APPDIR" || exit 9
rm -f .web/nocompile
echo "PRE: nocompile_exists=$([ -f .web/nocompile ] && echo yes || echo no)"
T0=$(date +%s.%N)
REFLEX_TELEMETRY_ENABLED=false setsid "$VENV/bin/reflex" run --backend-only --backend-port "$BP" "$@" > "$LOG" 2>&1 &
PID=$!
READY=""
for i in $(seq 1 240); do
  CODE=$(curl -s --noproxy '*' -m 3 -o /dev/null -w '%{http_code}' "http://localhost:$BP/ping" 2>/dev/null)
  if [ "$CODE" = "200" ]; then READY=$(echo "$(date +%s.%N) - $T0" | bc); break; fi
  kill -0 $PID 2>/dev/null || { echo "DIED EARLY rc=?"; break; }
  sleep 0.25
done
echo "TIME_TO_PING200=${READY:-NEVER}s pid=$PID"
sleep 3
echo "POST: nocompile_exists=$([ -f .web/nocompile ] && echo yes || echo no)"
echo "DEV_RELOAD_MARKER=$([ -f .web/.reflex_dev_backend_started ] && echo yes || echo no)"
# RSS of backend worker processes
echo "WORKER_PROCS:"; ps -eo pid,pgid,rss,comm,args --no-headers | awk -v g=$(ps -o pgid= -p $PID | tr -d ' ') '$2==g{printf "  pid=%s rss_kb=%s %s\n",$1,$3,substr($0, index($0,$5))}' | head -8
PGID=$(ps -o pgid= -p $PID 2>/dev/null | tr -d ' ')
kill -TERM $PID 2>/dev/null
for j in $(seq 1 200); do kill -0 $PID 2>/dev/null || { wait $PID; echo "EXIT_CODE=$?"; break; }; sleep 0.1; done
sleep 2
[ -n "$PGID" ] && kill -9 -$PGID 2>/dev/null
sleep 1
echo "FINAL: nocompile_exists=$([ -f .web/nocompile ] && echo yes || echo no)"
echo "PORTS:"; python3 "$PORTS_PY" "$BP" 2>/dev/null
echo "###END"
