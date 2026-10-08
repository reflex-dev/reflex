#!/usr/bin/env bash
# Usage: run_app.sh <appdir> <venv> <frontend_port> <backend_port> <logfile> [extra `reflex run` args]
# Starts `reflex run --loglevel debug` in its own session (setsid), records the pid in
# <appdir>/.server.pid and polls the frontend (and backend /ping) until both answer 200.
set -u
APPDIR=$1; VENV=$2; FP=$3; BP=$4; LOG=$5; shift 5
cd "$APPDIR" || exit 2
for p in $FP $BP; do
  if lsof -nP -iTCP:$p -sTCP:LISTEN -t >/dev/null 2>&1; then echo "PORT $p BUSY"; lsof -nP -iTCP:$p -sTCP:LISTEN; exit 2; fi
done
QA_EXPECT_VENV=$(basename "$VENV") REFLEX_TELEMETRY_ENABLED=false setsid "$VENV/bin/reflex" run --frontend-port "$FP" --backend-port "$BP" --loglevel debug "$@" > "$LOG" 2>&1 < /dev/null &
PID=$!
echo "$PID" > "$(dirname "$0")/../run/$(basename "$APPDIR").pid"
echo "started reflex pid=$PID ($(date +%T)) log=$LOG"
start=$(date +%s)
while true; do
  fc=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' --max-time 5 "http://localhost:$FP/")
  bc=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' --max-time 5 "http://localhost:$BP/ping")
  if [ "$fc" = "200" ] && [ "$bc" = "200" ]; then echo "UP after $(( $(date +%s) - start ))s (frontend $fc, backend /ping $bc)"; break; fi
  if ! kill -0 "$PID" 2>/dev/null; then echo "SERVER DIED after $(( $(date +%s) - start ))s"; tail -40 "$LOG"; exit 1; fi
  if [ $(( $(date +%s) - start )) -gt 420 ]; then echo "TIMEOUT (frontend $fc backend $bc)"; tail -40 "$LOG"; exit 1; fi
  sleep 3
done
