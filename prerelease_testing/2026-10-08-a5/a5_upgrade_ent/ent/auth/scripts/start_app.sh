#!/usr/bin/env bash
# Usage: start_app.sh <dev|prod> <logfile> [extra reflex args]   (env passed through to run_app.sh)
# Launches run_app.sh in its own session/process group; the PGID is written to run/app.pgid.
W=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/apps/a5_upgrade_ent/ent/auth
setsid "$W/scripts/run_app.sh" "$@" < /dev/null > /dev/null 2>&1 &
PID=$!
sleep 0.5
PGID=$(ps -o pgid= -p $PID | tr -d ' ')
echo "${PGID:-$PID}" > "$W/run/app.pgid"
echo "started pid=$PID pgid=${PGID:-$PID}"
