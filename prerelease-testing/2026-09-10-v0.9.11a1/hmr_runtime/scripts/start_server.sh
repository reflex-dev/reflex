#!/usr/bin/env bash
# Start `reflex run` for an app dir in the background and wait until the frontend answers 200.
# usage: start_server.sh <venv_dir> <app_dir> <frontend_port> <backend_port> <log_file> <pid_file> [--env prod] [EXTRA_ENV=1 ...]
# Extra KEY=VALUE args are exported into the server's environment (e.g. REFLEX_DEV_PROD_REACT=1).
set -u
VENV=$1; APP=$2; FP=$3; BP=$4; LOG=$5; PIDF=$6; shift 6
ARGS=()
for a in "$@"; do
  case "$a" in
    *=*) export "$a" ;;
    *) ARGS+=("$a") ;;
  esac
done
export REFLEX_TELEMETRY_ENABLED=false
cd "$APP" || exit 2
setsid nohup "$VENV/bin/reflex" run --loglevel debug --frontend-port "$FP" --backend-port "$BP" "${ARGS[@]}" >"$LOG" 2>&1 &
echo $! >"$PIDF"
echo "started pid $(cat "$PIDF") log $LOG"
for i in $(seq 1 240); do
  code=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' "http://localhost:$FP/" 2>/dev/null)
  if [ "$code" = "200" ]; then echo "frontend ready after ~${i}s (http $code)"; exit 0; fi
  if ! kill -0 "$(cat "$PIDF")" 2>/dev/null; then echo "server process exited early"; tail -30 "$LOG"; exit 1; fi
  sleep 1
done
echo "timeout waiting for frontend"; tail -30 "$LOG"; exit 1
