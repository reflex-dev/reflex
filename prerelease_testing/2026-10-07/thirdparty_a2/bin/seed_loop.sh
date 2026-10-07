#!/bin/bash
# Usage: seed_loop.sh <venv> <rundir> <label> <mode:dev|prod> <seed...>
# For each PYTHONHASHSEED: start tp_patterns, run drive_storage_only.py (F-003 repro), stop. Ports: dev 3500/8500, prod 3510 (single port).
SB=${SB:-/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad}
W=$SB/apps/thirdparty_a2
V=$1; APP=$2; LABEL=$3; MODE=$4; shift 4
for SEED in "$@"; do
  LOG=$W/logs/tp_patterns-$LABEL-$MODE-seed$SEED.log
  if [ "$MODE" = prod ]; then
    PYTHONHASHSEED=$SEED REFLEX_API_URL=http://localhost:3510 $W/bin/start_app.sh $V $APP 3510 3510 $LOG --env prod >/dev/null
    URL=http://localhost:3510
  else
    PYTHONHASHSEED=$SEED $W/bin/start_app.sh $V $APP 3500 8500 $LOG >/dev/null
    URL=http://localhost:3500
  fi
  PIDF=$W/pids/$(basename $APP)-$V.pid
  $W/bin/wait_up.sh $URL/ 400 $PIDF || { $W/bin/stop_app.sh $PIDF; continue; }
  sleep 3
  echo -n "seed=$SEED mode=$MODE $LABEL  "
  (cd $W/drivers && NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 timeout 120 $SB/envs/driver/bin/python drive_storage_only.py $URL) 2>&1 | tail -1
  $W/bin/stop_app.sh $PIDF >/dev/null
  sleep 1
done
