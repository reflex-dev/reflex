#!/bin/bash
# Usage: start_app.sh <alpha|stable> <app_dir> <frontend_port> <backend_port> <log_file> [extra reflex run args...]
# Starts `reflex run` in its own session (process group); pidfile in $W/pids/<venv>.pid. Extra env passes through.
set -u
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/verify_thirdparty_0
V=$1; APP=$2; FP=$3; BP=$4; LOG=$5; shift 5
cd "$APP" || exit 1
export REFLEX_TELEMETRY_ENABLED=false
setsid $SB/envs/$V/bin/reflex run --frontend-port $FP --backend-port $BP "$@" > "$LOG" 2>&1 < /dev/null &
echo $! > $W/pids/$V.pid
echo "started pgid=$! venv=$V app=$APP fp=$FP bp=$BP log=$LOG"
