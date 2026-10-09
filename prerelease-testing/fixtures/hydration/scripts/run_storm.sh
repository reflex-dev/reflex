#!/bin/bash
# Usage: run_storm.sh <venv> <dev|prod> <runs> <FP> <BP> [PARTS=S] [NTABS=6] -- bootecho + sync_race.py Part S (and/or R) N times
. "$(dirname "$0")/env.sh"
V=$1; MODE=$2; N=$3; FP=$4; BP=$5; PARTS=${6:-S}; NT=${7:-6}
O=$W/results/sync; mkdir -p $O; cd $O
$F/scripts/srv.sh start st-$V-$MODE $V $MODE $F/src/bootecho $FP $BP > /dev/null || exit 1
$NP $DRV $F/drivers/waitsrv.py 400 http://localhost:$FP/ http://localhost:$BP/ping > /dev/null || exit 1
sleep 4
for i in $(seq 1 $N); do
  echo "--- $V $MODE run $i"
  $NP timeout 200 $DRV $F/drivers/sync_race.py http://localhost:$FP storm_${V}_${MODE}_${PARTS}_${NT}_$i.json 2500 $NT $PARTS 2>&1 | grep -E "^(R|S):" | cut -c1-420
done
$F/scripts/srv.sh stop st-$V-$MODE > /dev/null
