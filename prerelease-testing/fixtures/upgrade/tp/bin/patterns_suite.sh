#!/bin/bash
# Usage: patterns_suite.sh <venv> <rundir> <label> <dev|prod> [seed]
# Starts tp_patterns, runs drive_patterns + drive_classassign + drive_storage_only, stops it. Dev 3463/8463, prod 8467 single port.
. "$(dirname "$0")/../../bin/env.sh"; W=$(cd "$(dirname "$0")/.." && pwd)
V=$1; APP=$2; LABEL=$3; MODE=$4; SEED=${5:-}
export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
LOG=$W/logs/tp_patterns-$LABEL-$MODE.log
[ -n "$SEED" ] && export PYTHONHASHSEED=$SEED
if [ "$MODE" = prod ]; then
  REFLEX_API_URL=http://localhost:8467 $W/bin/start_app.sh $V $APP 8467 8467 $LOG --env prod >/dev/null; URL=http://localhost:8467
else
  $W/bin/start_app.sh $V $APP 3463 8463 $LOG >/dev/null; URL=http://localhost:3463
fi
PIDF=$W/pids/$(basename $APP)-$V.pid
$W/bin/wait_up.sh $URL/ 400 $PIDF || { $W/bin/stop_app.sh $PIDF; exit 1; }
sleep 3
cd $W/drivers
timeout 300 $DPY drive_patterns.py $URL $W/out/patterns $LABEL-$MODE 2>&1 | grep -E "^(PASS|FAIL|SUMMARY|  ANOMALY)" | cut -c1-330
timeout 200 $DPY drive_classassign.py $URL $W/out/patterns/$LABEL-$MODE-classassign.json $LABEL-$MODE 2>&1 | grep -E "^(PASS|FAIL|SUMMARY)" | cut -c1-260
echo -n "storage_only: "; timeout 100 $DPY drive_storage_only.py $URL
$W/bin/stop_app.sh $PIDF
