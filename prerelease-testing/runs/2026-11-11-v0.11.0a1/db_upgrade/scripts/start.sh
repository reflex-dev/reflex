#!/usr/bin/env bash
# start.sh <key> <appdir> <fp> <bp> <log> [extra reflex run args]  (prod: fp==bp, set REFLEX_API_URL in caller env)
set -u; . "$(dirname "$0")/env.sh"
KEY=$1; A=$2; FP=$3; BP=$4; LOG=$5; shift 5; V=$(venv "$KEY")
for p in $FP $BP; do if port_busy $p; then echo "PORT $p BUSY"; exit 2; fi; done
cd "$A" || exit 2
setsid "$V/bin/reflex" run --frontend-port "$FP" --backend-port "$BP" --loglevel debug "$@" > "$LOG" 2>&1 < /dev/null &
PID=$!; echo "$PID" > "$W/logs/$(basename "$A").pid"; echo "started pid=$PID log=$LOG"
start=$(date +%s)
while true; do
  fc=$(http_code "http://localhost:$FP/"); bc=$(http_code "http://localhost:$BP/ping")
  [ "$fc" = 200 ] && [ "$bc" = 200 ] && { echo "UP after $(( $(date +%s)-start ))s"; exit 0; }
  kill -0 $PID 2>/dev/null || { echo "SERVER DIED"; tail -30 "$LOG"; exit 1; }
  [ $(( $(date +%s)-start )) -gt 420 ] && { echo "TIMEOUT fe=$fc be=$bc"; tail -30 "$LOG"; exit 1; }
  sleep 3
done
