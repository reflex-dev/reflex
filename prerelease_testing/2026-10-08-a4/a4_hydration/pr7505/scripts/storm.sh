#!/bin/bash
# storm.sh <fix|a3> <dev|prod> <runs> [NTABS=6]: bootecho + sync_race.py part S, ports 3150/8150 (prod: 3150)
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; A=$SB/apps/a311
V=$1; MODE=$2; N=$3; NT=${4:-6}; FP=3150; BP=8150; [ $MODE = prod ] && BP=3150
if [ $V = fix ]; then RX=/home/user/wt-a3-11/.venv/bin/reflex; ENVN=a311fix; else RX=$SB/envs/a3/bin/reflex; ENVN=a3; fi
API=http://localhost:$BP
cd $A/run-$V
setsid env REFLEX_TELEMETRY_ENABLED=false REFLEX_API_URL=$API RVH_VENV=$ENVN $RX run --env $MODE --frontend-port $FP --backend-port $BP > $A/logs/$V-$MODE.log 2>&1 < /dev/null & pid=$!
NP="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1"; DRV=$SB/envs/driver/bin/python
$NP $DRV $SB/apps/a3_hydration/drivers/waitsrv.py 400 http://localhost:$FP/ http://localhost:$BP/ping > /dev/null || { echo "server not up"; tail -20 $A/logs/$V-$MODE.log; kill -TERM -- -$pid; exit 1; }
sleep 4
for i in $(seq 1 $N); do
  echo "--- $V $MODE run $i"
  $NP timeout 200 $DRV $SB/apps/a3_hydration/drivers/sync_race.py http://localhost:$FP $A/out/storm_${V}_${MODE}_${NT}_$i.json 2500 $NT S 2>&1 | grep -E "^S:" | cut -c1-600
done
kill -TERM -- -$pid; sleep 3; kill -KILL -- -$pid 2>/dev/null; true
