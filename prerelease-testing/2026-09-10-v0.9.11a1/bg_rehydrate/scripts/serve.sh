#!/bin/bash
# Usage: serve.sh <venv> <appdir> <label> <frontend_port> <backend_port> [--env prod] [extra reflex run args]
# Extra env for the server is taken from the caller's environment (REFLEX_REDIS_URL, REFLEX_REDIS_TOKEN_EXPIRATION, ...).
# Writes logs/<label>.log and logs/<label>.pid. Waits for the frontend to answer 200.
set -u
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
A=$SB/apps/bg_rehydrate
VENV=$1; APPDIR=$2; LABEL=$3; FP=$4; BP=$5; shift 5
LOG=$A/logs/$LABEL.log
cd "$APPDIR" || exit 1
REFLEX_TELEMETRY_ENABLED=false nohup "$SB/envs/$VENV/bin/reflex" run --frontend-port "$FP" --backend-port "$BP" --loglevel debug "$@" > "$LOG" 2>&1 &
echo $! > "$A/logs/$LABEL.pid"
echo "started pid=$(cat $A/logs/$LABEL.pid) log=$LOG"
for i in $(seq 1 180); do
  code=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' "http://localhost:$FP/" 2>/dev/null)
  bcode=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' "http://localhost:$BP/ping" 2>/dev/null)
  if [ "$code" = "200" ] && [ "$bcode" = "200" ]; then echo "up after ${i}x2s (frontend=$code backend=$bcode)"; exit 0; fi
  if ! kill -0 "$(cat $A/logs/$LABEL.pid)" 2>/dev/null; then echo "process died"; tail -30 "$LOG"; exit 1; fi
  sleep 2
done
echo "timeout waiting for server"; tail -30 "$LOG"; exit 1
