#!/bin/bash
# Usage: start_app.sh <venv-name> <app_dir> <frontend_port> <backend_port> <log_file> [extra reflex run args...]
# Starts `reflex run` in its own session (process group); pidfile $W/pids/<PIDTAG or venv>.pid
set -u
. "$(cd "$(dirname "$0")/.." && pwd)/env.sh"
V=$1; APP=$2; P_FP=$3; P_BP=$4; LOG=$5; shift 5
: "${PORT_LO_F:=3300}" "${PORT_HI_F:=3339}" "${PORT_LO_B:=8300}" "${PORT_HI_B:=8339}"
for p in $P_FP $P_BP; do
  if ! { [ "$p" -ge "$PORT_LO_F" ] && [ "$p" -le "$PORT_HI_F" ]; } && ! { [ "$p" -ge "$PORT_LO_B" ] && [ "$p" -le "$PORT_HI_B" ]; }; then
    echo "port $p outside $PORT_LO_F-$PORT_HI_F/$PORT_LO_B-$PORT_HI_B"; exit 1; fi
done
TAG=${PIDTAG:-$V}
export EXPECT_VENV=$V   # app-level venv guards (apps/n024doc) read it
cd "$APP" || exit 1
setsid "$SB/envs/$V/bin/reflex" run --frontend-port "$P_FP" --backend-port "$P_BP" "$@" > "$LOG" 2>&1 < /dev/null &
echo $! > "$W/pids/$TAG.pid"
echo "started pgid=$! venv=$V app=$APP fp=$P_FP bp=$P_BP log=$LOG pidfile=$W/pids/$TAG.pid"
