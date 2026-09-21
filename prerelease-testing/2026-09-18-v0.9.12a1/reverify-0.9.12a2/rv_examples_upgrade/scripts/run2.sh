#!/bin/bash
# usage: run2.sh <appdir> <venv> <fp> <bp> <logfile> [extra reflex args]
set -u
APPDIR=$1; VENV=$2; FP=$3; BP=$4; LOG=$5; shift 5
# refuse to start if the port is already bound
if curl -s --noproxy '*' -o /dev/null -m 2 "http://localhost:$FP/" 2>/dev/null; then
  echo "PORT $FP ALREADY BOUND - aborting"; exit 2
fi
cd "$APPDIR" || exit 1
REFLEX_TELEMETRY_ENABLED=false nohup "$VENV/bin/reflex" run --frontend-port "$FP" --backend-port "$BP" "$@" > "$LOG" 2>&1 &
PID=$!
echo "PID=$PID"
for i in $(seq 1 120); do
  code=$(curl -s --noproxy '*' -o /dev/null -w "%{http_code}" "http://localhost:$FP/" 2>/dev/null)
  if [ "$code" = "200" ]; then echo "UP after ${i}x4s"; exit 0; fi
  if ! kill -0 $PID 2>/dev/null; then echo "DIED"; tail -30 "$LOG"; exit 1; fi
  sleep 4
done
echo "TIMEOUT"; tail -30 "$LOG"; exit 1
