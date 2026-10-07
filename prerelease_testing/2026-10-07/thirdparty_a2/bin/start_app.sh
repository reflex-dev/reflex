#!/bin/bash
# Usage: start_app.sh <venv-name> <app_dir> <frontend_port> <backend_port> <log_file> [extra reflex run args...]
# <venv-name> is a directory under $SB/envs (e.g. thirdparty_a2-a2, thirdparty-alpha, thirdparty-stable).
# Starts `reflex run` in its own session (process group) and records the PGID in pids/.
set -u
SB=${SB:-/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad}
W=$SB/apps/thirdparty_a2
V=$1; APP=$2; FP=$3; BP=$4; LOG=$5; shift 5
cd "$APP" || exit 1
export REFLEX_TELEMETRY_ENABLED=false
mkdir -p $W/pids
setsid $SB/envs/$V/bin/reflex run --frontend-port $FP --backend-port $BP "$@" > "$LOG" 2>&1 < /dev/null &
PID=$!
echo $PID > $W/pids/$(basename $APP)-$V.pid
echo "started pid=$PID (pgid) venv=$V app=$APP fp=$FP bp=$BP log=$LOG"
