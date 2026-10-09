#!/usr/bin/env bash
# Usage: start_app.sh <dev|prod> <logfile> [extra reflex args]   (env passed through to run_app.sh)
# Launches run_app.sh in its own session/process group; the PGID goes to $WORK/auth/run/app.pgid (bin/stop_app.sh kills it).
. "$(dirname "$0")/../../lib.sh"; W=$WORK/auth; mkdir -p "$W/run"
setsid "$FX/auth/scripts/run_app.sh" "$@" < /dev/null > /dev/null 2>&1 &
PID=$!
sleep 0.5
PGID=$(ps -o pgid= -p $PID | tr -d ' ')
echo "${PGID:-$PID}" > "$W/run/app.pgid"
echo "started pid=$PID pgid=${PGID:-$PID}"
