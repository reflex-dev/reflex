#!/bin/bash
# Usage: start_app.sh <alpha|stable> <app_dir> <frontend_port> <backend_port> <log_file> [extra reflex run args...]
# Starts `reflex run` in its own session (process group) and records the PGID in pids/.
set -u
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
V=$1; APP=$2; FP=$3; BP=$4; LOG=$5; shift 5
cd "$APP" || exit 1
export REFLEX_TELEMETRY_ENABLED=false
setsid $SB/envs/thirdparty-$V/bin/reflex run --frontend-port $FP --backend-port $BP "$@" > "$LOG" 2>&1 < /dev/null &
PID=$!
echo $PID > $SB/apps/thirdparty/pids/$(basename $APP)-$V.pid
echo "started pid=$PID (pgid) app=$APP fp=$FP bp=$BP log=$LOG"
