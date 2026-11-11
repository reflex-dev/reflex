#!/bin/bash
# usage: run.sh <venv> <appdir> <logfile> <mode dev|prod> [extra reflex args]
SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad
V=$1; APP=$2; LOG=$3; MODE=$4; shift 4
cd $APP || exit 1
export REFLEX_TELEMETRY_ENABLED=false
for p in 3140 8140 3141; do curl -s --noproxy '*' -o /dev/null localhost:$p && { echo "port $p busy"; exit 1; }; done
if [ "$MODE" = prod ]; then
  REFLEX_API_URL=http://localhost:3141 setsid $SB/envs/$V/bin/reflex run --env prod --frontend-port 3141 --backend-port 3141 "$@" > $LOG 2>&1 < /dev/null &
else
  setsid $SB/envs/$V/bin/reflex run --frontend-port 3140 --backend-port 8140 "$@" > $LOG 2>&1 < /dev/null &
fi
echo $! > $APP/.pgid
echo started pgid $(cat $APP/.pgid)
