#!/bin/bash
# stamp.sh <fix|a3> <dev|prod> <runs> <NTABS>: syncstamp /stamp, ports 3151/8151
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; A=$SB/apps/a311
V=$1; MODE=$2; N=$3; NT=$4; FP=3151; BP=8151; [ $MODE = prod ] && BP=3151
if [ $V = fix ]; then RX=/home/user/wt-a3-11/.venv/bin/reflex; ENVN=a311fix; else RX=$SB/envs/a3/bin/reflex; ENVN=a3; fi
cd $A/stamp-$V
setsid env REFLEX_TELEMETRY_ENABLED=false REFLEX_API_URL=http://localhost:$BP RVH_VENV=$ENVN $RX run --env $MODE --frontend-port $FP --backend-port $BP > $A/logs/stamp-$V-$MODE.log 2>&1 < /dev/null & pid=$!
NP="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1"; DRV=$SB/envs/driver/bin/python
$NP $DRV $SB/apps/a3_hydration/drivers/waitsrv.py 400 http://localhost:$FP/ http://localhost:$BP/ping > /dev/null || { echo "server not up"; tail -20 $A/logs/stamp-$V-$MODE.log; kill -TERM -- -$pid; exit 1; }
sleep 4
for i in $(seq 1 $N); do
  echo -n "$V $MODE n=$NT run $i: "
  $NP timeout 200 $DRV $SB/apps/a3_hydration/drivers/stamp_storm.py http://localhost:$FP /stamp $NT $A/out/stamp_${V}_${MODE}_${NT}_$i.json 10 2>&1 | tail -1 | cut -c1-400
done
kill -TERM -- -$pid; sleep 3; kill -KILL -- -$pid 2>/dev/null; true
