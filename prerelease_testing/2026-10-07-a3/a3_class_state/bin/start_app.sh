#!/bin/bash
# Usage: start_app.sh <venv-name> <app_dir> <frontend_port> <backend_port> <log_file> [extra reflex run args...]
# Starts `reflex run` in its own session (process group); pidfile $W/pids/<PIDTAG or venv>.pid
set -u
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/a3_class_state
V=$1; APP=$2; FP=$3; BP=$4; LOG=$5; shift 5
case "$FP$BP" in *3000*|*8000*) echo "refusing reserved port"; exit 1;; esac
for p in $FP $BP; do if [ $p -lt 3100 ] || { [ $p -gt 3119 ] && [ $p -lt 8100 ]; } || [ $p -gt 8119 ]; then echo "port $p outside 3100-3119/8100-8119"; exit 1; fi; done
TAG=${PIDTAG:-$V}
cd "$APP" || exit 1
export REFLEX_TELEMETRY_ENABLED=false
setsid $SB/envs/$V/bin/reflex run --frontend-port $FP --backend-port $BP "$@" > "$LOG" 2>&1 < /dev/null &
echo $! > $W/pids/$TAG.pid
echo "started pgid=$! venv=$V app=$APP fp=$FP bp=$BP log=$LOG pidfile=$W/pids/$TAG.pid"
