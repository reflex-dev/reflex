#!/bin/bash
# Usage: run_server.sh <app> <frontend_port> <backend_port> <logname> [extra reflex run args]
# Starts `reflex run` for $C/<app> in its own session (setsid) using the per-app venv
# $SB/envs/up_counter_todo_clock_<app> and a PRIVATE REFLEX_DIR=$SB/envs/rxdir_<app> (so each
# app's reflex installs/manages its own bun, exactly as a user's first run would).
# Logs go to $C/logs/server/<app>_<logname>.log — OUTSIDE the app dir, because reflex's
# granian reloader watches every top-level dir of the app (a <app>/logs dir triggers reloads).
# Writes $C/logs/server/<app>_<logname>.pid
set -u
SB=${SB:-/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad}
C=$SB/apps/up_counter_todo_clock
APP=$1; FP=$2; BP=$3; LOG=$4; shift 4
VENV=$SB/envs/up_counter_todo_clock_$APP
cd $C/$APP || exit 1
mkdir -p $C/logs/server
LOGFILE=$C/logs/server/${APP}_$LOG.log
REFLEX_DIR=$SB/envs/rxdir_$APP REFLEX_TELEMETRY_ENABLED=false setsid $VENV/bin/reflex run --frontend-port $FP --backend-port $BP --loglevel debug "$@" > $LOGFILE 2>&1 < /dev/null &
PID=$!
echo $PID > $C/logs/server/${APP}_$LOG.pid
echo "started $APP pid=$PID (pgid=$(ps -o pgid= -p $PID | tr -d ' ')) log=$LOGFILE"
