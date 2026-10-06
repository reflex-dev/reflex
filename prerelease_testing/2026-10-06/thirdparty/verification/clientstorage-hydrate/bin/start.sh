#!/bin/bash
# Usage: start.sh <venv-name> <app_dir> <frontend_port> <backend_port> <log_file> [extra reflex run args...]
# Starts `reflex run` in its own session (process group); pidfile in $W/pids/<app>-<venv>.pid
set -u
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/verify_thirdparty_1
V=$1; APP=$2; FP=$3; BP=$4; LOG=$5; shift 5
case "$FP$BP" in *36[0-9][0-9]*|*86[0-9][0-9]*) ;; esac
for p in $FP $BP; do if [ $p -lt 3604 ] || { [ $p -gt 3607 ] && [ $p -lt 8604 ]; } || [ $p -gt 8607 ]; then echo "PORT $p OUT OF RANGE"; exit 3; fi; done
cd "$APP" || exit 1
export REFLEX_TELEMETRY_ENABLED=false VERIFY_VENV=$V
setsid $SB/envs/$V/bin/reflex run --frontend-port $FP --backend-port $BP "$@" > "$LOG" 2>&1 < /dev/null &
PID=$!
echo $PID > $W/pids/$(basename $APP)-$V.pid
echo "started pid=$PID venv=$V app=$APP fp=$FP bp=$BP log=$LOG args=$* PYTHONHASHSEED=${PYTHONHASHSEED:-unset}"
