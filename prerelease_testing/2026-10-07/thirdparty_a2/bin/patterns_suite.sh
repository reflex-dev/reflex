#!/bin/bash
# Usage: patterns_suite.sh <venv> <rundir> <label> <dev|prod> [seed]
# Starts tp_patterns, runs drive_patterns + drive_classassign + drive_storage_only, stops it. Dev 3500/8500, prod 3510 single port.
SB=${SB:-/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad}
W=$SB/apps/thirdparty_a2
V=$1; APP=$2; LABEL=$3; MODE=$4; SEED=${5:-}
export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
LOG=$W/logs/tp_patterns-$LABEL-$MODE.log
[ -n "$SEED" ] && export PYTHONHASHSEED=$SEED
if [ "$MODE" = prod ]; then
  REFLEX_API_URL=http://localhost:3510 $W/bin/start_app.sh $V $APP 3510 3510 $LOG --env prod >/dev/null; URL=http://localhost:3510
else
  $W/bin/start_app.sh $V $APP 3500 8500 $LOG >/dev/null; URL=http://localhost:3500
fi
PIDF=$W/pids/$(basename $APP)-$V.pid
$W/bin/wait_up.sh $URL/ 400 $PIDF || { $W/bin/stop_app.sh $PIDF; exit 1; }
sleep 3
cd $W/drivers
timeout 300 $SB/envs/driver/bin/python drive_patterns.py $URL $W/out/patterns $LABEL-$MODE 2>&1 | grep -E "^(PASS|FAIL|SUMMARY|  ANOMALY)" | cut -c1-330
timeout 200 $SB/envs/driver/bin/python drive_classassign.py $URL $W/out/patterns/$LABEL-$MODE-classassign.json $LABEL-$MODE 2>&1 | grep -E "^(PASS|FAIL|SUMMARY)" | cut -c1-260
echo -n "storage_only: "; timeout 100 $SB/envs/driver/bin/python drive_storage_only.py $URL
$W/bin/stop_app.sh $PIDF
