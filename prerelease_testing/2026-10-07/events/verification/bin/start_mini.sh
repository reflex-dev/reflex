#!/usr/bin/env bash
# usage: start_mini.sh <venv> <disk|redis>   -- the EXPLORER's unmodified mini app, on MY dev ports (3640/8640)
set -u
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/verify_events_0
VENV=$1; SM=$2
RUN=$W/run/theirs_mini_${VENV}_dev
LABEL=theirs_mini_${VENV}_dev_${SM}
mkdir -p $RUN $W/logs $W/pids
rm -rf $RUN/mini $RUN/rxconfig.py; cp -r $W/theirs/src/mini/mini $RUN/mini; cp $W/theirs/src/mini/rxconfig.py $RUN/rxconfig.py
cd $RUN || exit 1
unset REFLEX_REDIS_URL REFLEX_STATE_MANAGER_MODE GRANIAN_WORKERS
export REFLEX_TELEMETRY_ENABLED=false EV_FP=3640 EV_BP=8640
[ "$SM" = redis ] && export REFLEX_REDIS_URL=redis://localhost:8659
setsid nohup $SB/envs/$VENV/bin/reflex run --env dev --frontend-port 3640 --backend-port 8640 --loglevel debug > $W/logs/$LABEL.log 2>&1 < /dev/null &
echo $! > $W/pids/$LABEL.pid
echo "[start_mini] label=$LABEL pid=$(cat $W/pids/$LABEL.pid) redis=${REFLEX_REDIS_URL:-}"
