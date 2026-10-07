#!/usr/bin/env bash
# Usage: start_server.sh <venv> <app_dir> <log_file> <poll_url> -- <reflex run args...>
# Starts `reflex run` in its own session (setsid) so the whole process group can be killed.
set -u
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
VENV=$1; APP=$2; LOG=$3; URL=$4; shift 4; [ "$1" = "--" ] && shift
cd "$APP" || exit 2
export CI=true REFLEX_TELEMETRY_ENABLED=false
setsid "$SB/envs/$VENV/bin/reflex" run "$@" > "$LOG" 2>&1 < /dev/null &
PID=$!
echo "$PID" > "$SB/apps/ent_grid/pids/current.pid"
echo "started pid/pgid=$PID venv=$VENV app=$APP args=$*"
for i in $(seq 1 120); do
  if ! kill -0 "$PID" 2>/dev/null; then echo "server exited early"; tail -40 "$LOG"; exit 1; fi
  code=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' --max-time 5 "$URL" || true)
  if [ "$code" = "200" ]; then echo "UP after ~$((i*3))s ($URL -> $code)"; exit 0; fi
  sleep 3
done
echo "TIMEOUT waiting for $URL"; tail -40 "$LOG"; exit 1
