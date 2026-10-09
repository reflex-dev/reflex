#!/bin/bash
# Usage: run_f002.sh <venv> <dev|prod> <label> <FP> <BP> [ENV=VAL...]
# F-002 suite on f1combo: fresh x2 (nothing may be written), returning visitor after every default changed (v2),
# fresh v2, sync=True two-tab race. Results in $W/results/f002/<label>_*.json, stdout summary.
. "$(dirname "$0")/env.sh"
V=$1; MODE=$2; L=$3; FP=$4; BP=$5; shift 5
O=$W/results/f002; mkdir -p $O; cd $O
IDS=pl-ls,wu-ls,wu-sync,cs-ls,cu-ls,ws-ls,wt-ls
NAME=f1-$L
$F/scripts/srv.sh start $NAME $V $MODE $F/src/f1combo $FP $BP "$@" || exit 1
$NP $DRV $F/drivers/waitsrv.py 400 http://localhost:$FP/ http://localhost:$BP/ping || exit 1
sleep 2
echo "== fresh_1"; $NP $DRV $F/drivers/f1_check.py http://localhost:$FP/ - ${L}_state1.json ${L}_fresh_1.json $IDS
echo "== fresh_2"; $NP $DRV $F/drivers/f1_check.py http://localhost:$FP/ - ${L}_state2.json ${L}_fresh_2.json $IDS
echo "== returning_same (state1, same build)"; $NP $DRV $F/drivers/f1_check.py http://localhost:$FP/ ${L}_state1.json - ${L}_returning_same.json $IDS
echo "== sync tabs"; $NP $DRV $F/drivers/f1_sync_tabs.py http://localhost:$FP/ ${L}_sync.json 2500 | tail -5
$F/scripts/srv.sh stop $NAME
$F/scripts/srv.sh start $NAME $V $MODE $F/src/v2/f1combo $FP $BP "$@" || exit 1
sleep 3; $NP $DRV $F/drivers/waitsrv.py 400 http://localhost:$FP/ http://localhost:$BP/ping || exit 1
sleep 2
echo "== v2 returning (state1 from v1)"; $NP $DRV $F/drivers/f1_check.py http://localhost:$FP/ ${L}_state1.json - ${L}_v2_returning.json $IDS
echo "== v2 fresh"; $NP $DRV $F/drivers/f1_check.py http://localhost:$FP/ - - ${L}_v2_fresh.json $IDS
$F/scripts/srv.sh stop $NAME
