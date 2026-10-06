#!/bin/bash
# Usage: start_server.sh <alpha|stable> <dev|prod> <logname>
# dev: frontend/backend ports per version; prod: single port.
set -u
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/dataeditor_components
V=$1; MODE=$2; LOG=$W/logs/$3.log
case "$V-$MODE" in
  alpha-dev) FP=3420; BP=8420;;
  alpha-prod) FP=3421; BP=3421;;
  stable-dev) FP=3422; BP=8422;;
  stable-prod) FP=3423; BP=3423;;
esac
cd $W/app-$V
export REFLEX_TELEMETRY_ENABLED=false
if [ "$MODE" = prod ]; then
  CLUSTER_API_URL=http://localhost:$FP nohup $SB/envs/dataeditor_components-$V/bin/reflex run --env prod --frontend-port $FP --backend-port $BP --loglevel debug > $LOG 2>&1 &
else
  CLUSTER_API_URL=http://localhost:$BP nohup $SB/envs/dataeditor_components-$V/bin/reflex run --frontend-port $FP --backend-port $BP --loglevel debug > $LOG 2>&1 &
fi
echo $! > $W/logs/server-$V-$MODE.pid
echo "started pid $(cat $W/logs/server-$V-$MODE.pid) fp=$FP bp=$BP log=$LOG"
