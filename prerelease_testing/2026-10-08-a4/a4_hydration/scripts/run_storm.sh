#!/bin/bash
# Usage: run_storm.sh <venv> <dev|prod> <runs> <FP> <BP> [PARTS=S] [NTABS=6] -- bootecho + sync_race.py Part S (and/or R) N times
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a4_hydration
V=$1; MODE=$2; N=$3; FP=$4; BP=$5; PARTS=${6:-S}; NT=${7:-6}
NP="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1"; DRV=$SB/envs/driver/bin/python
O=$W/results/sync; mkdir -p $O; cd $O
$W/scripts/srv.sh start st-$V-$MODE $V $MODE $W/src/bootecho $FP $BP > /dev/null
$NP $DRV $W/drivers/waitsrv.py 400 http://localhost:$FP/ http://localhost:$BP/ping > /dev/null || exit 1
sleep 4
for i in $(seq 1 $N); do
  echo "--- $V $MODE run $i"
  $NP timeout 200 $DRV $W/drivers/sync_race.py http://localhost:$FP storm_${V}_${MODE}_${PARTS}_${NT}_$i.json 2500 $NT $PARTS 2>&1 | grep -E "^(R|S):" | cut -c1-420
done
$W/scripts/srv.sh stop st-$V-$MODE > /dev/null
