#!/bin/bash
# serve.sh <app_dir> <venv> <FP> <BP> <log> [extra reflex run args...]
APP="$1"; VENV="$2"; FP="$3"; BP="$4"; LOG="$5"; shift 5
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
mkdir -p "$(dirname "$LOG")" "$SB/reflex_dirs/v2ulf_$(basename "$APP")"
cd "$APP" || exit 1
env -u NO_PROXY -u no_proxy \
  REFLEX_DIR="$SB/reflex_dirs/v2ulf_$(basename "$APP")" \
  REFLEX_TELEMETRY_ENABLED=false \
  setsid "$VENV/bin/reflex" run --frontend-port "$FP" --backend-port "$BP" "$@" \
  > "$LOG" 2>&1 &
PID=$!
echo "$PID" > "$APP/server.pid"
echo "started pid=$PID (pgid $(ps -o pgid= -p $PID | tr -d ' ')) log=$LOG"
for i in $(seq 1 150); do
  code=$(curl -s -o /dev/null -w '%{http_code}' --noproxy '*' --max-time 5 "http://localhost:$FP/" || true)
  if [ "$code" = "200" ]; then echo "frontend up after ${i}*3s"; exit 0; fi
  if ! kill -0 "$PID" 2>/dev/null; then echo "SERVER DIED"; tail -30 "$LOG"; exit 1; fi
  sleep 3
done
echo "TIMEOUT waiting for frontend"; tail -40 "$LOG"; exit 1
