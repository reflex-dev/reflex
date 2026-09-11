#!/usr/bin/env bash
# usage: run_once.sh <reflex-bin> <appdir> <logfile> <fp> <bp>
set -u
BIN=$1; APP=$2; LOG=$3; FP=$4; BP=$5
cd "$APP" || exit 2
REFLEX_TELEMETRY_ENABLED=false setsid "$BIN" run --frontend-port "$FP" --backend-port "$BP" --loglevel debug > "$LOG" 2>&1 &
PID=$!
echo "pid=$PID pgid=$(ps -o pgid= -p $PID | tr -d ' ')"
for i in $(seq 1 180); do
  if grep -q "App running at" "$LOG" 2>/dev/null; then echo "READY after ${i}s"; break; fi
  if ! kill -0 $PID 2>/dev/null; then echo "DIED after ${i}s"; break; fi
  sleep 1
done
PGID=$(ps -o pgid= -p $PID 2>/dev/null | tr -d ' ')
[ -n "${PGID:-}" ] && kill -TERM -"$PGID" 2>/dev/null
sleep 3
[ -n "${PGID:-}" ] && kill -KILL -"$PGID" 2>/dev/null
wait $PID 2>/dev/null
echo "stopped"
