#!/bin/bash
# usage: serve.sh <app_dir> <venv_dir> <FP> <BP> <log> [extra reflex run args]
set -u
APP=$1; VENV=$2; FP=$3; BP=$4; LOG=$5; shift 5
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
cd "$APP" || exit 2
mkdir -p logs "$(dirname "$LOG")"
REFLEX_DIR="$SB/reflex_dirs/v2ulf1_$(basename "$APP")" REFLEX_TELEMETRY_ENABLED=false \
  setsid "$VENV/bin/reflex" run --frontend-port "$FP" --backend-port "$BP" --loglevel debug "$@" > "$LOG" 2>&1 &
PID=$!
echo "$PID" > logs/server.pid
echo "started pgid=$PID log=$LOG"
for i in $(seq 1 90); do
  code=$(curl -s -o /dev/null -w '%{http_code}' --noproxy '*' "http://localhost:$FP/" 2>/dev/null)
  if [ "$code" = "200" ]; then echo "UP after ~$((i*5))s"; exit 0; fi
  if ! kill -0 "$PID" 2>/dev/null; then echo "SERVER EXITED"; tail -30 "$LOG"; exit 1; fi
  sleep 5
done
echo "TIMEOUT http://localhost:$FP/"; tail -30 "$LOG"; exit 1
