#!/bin/bash
# Usage: start.sh <venv> <dev|prod> <label> [app=evapp] [redis]
# Copies src/<app> to run/<label>, starts the pausable proxy and `reflex run` on the
# cluster's reserved ports, logs to logs/<label>.log, writes pids/<label>.*.pid.
# Ports: evapp dev FE 3460 / BE 8460 / proxy 8462; evapp prod 8465 / proxy 8466;
#        mini dev FE 3470 / BE 8470 / proxy 8472; mini prod 8475 / proxy 8476; redis 8469.
set -e
. "$(dirname "$0")/../../bin/env.sh"
W=$(cd "$(dirname "$0")/.." && pwd)
V=$1; M=$2; L=$3; APP=${4:-evapp}; REDIS=${5:-}
case "$APP-$M" in
  evapp-dev) FP=3460; BP=8460; PX=8462;;
  evapp-prod) FP=8465; BP=8465; PX=8466;;
  mini-dev) FP=3470; BP=8470; PX=8472;;
  mini-prod) FP=8475; BP=8475; PX=8476;;
  n024doc-dev) FP=3474; BP=8474; PX=8473;;
  n024doc-prod) FP=8477; BP=8477; PX=8478;;
  bootdup-dev) FP=3474; BP=8474; PX=8473;;
  bootdup-prod) FP=8477; BP=8477; PX=8478;;
esac
RUN=$W/run/$L
mkdir -p "$RUN" "$W/logs" "$W/pids"
cp -r "$W/src/$APP/." "$RUN/"
echo up > "$W/pids/$L.proxystate"
nohup "$DPY" "$W/tools/tcpproxy.py" $PX $BP "$W/pids/$L.proxystate" > "$W/logs/$L.proxy.log" 2>&1 &
echo $! > "$W/pids/$L.proxy.pid"
cd "$RUN"
export EV_EXPECT_VENV=$V REFLEX_TELEMETRY_ENABLED=false LOGLEVEL=debug EV_FP=$FP EV_BP=$BP EV_API_URL=http://localhost:$PX
if [ -n "$REDIS" ]; then export REFLEX_REDIS_URL=redis://localhost:8469; fi
setsid nohup "$SB/envs/$V/bin/reflex" run --env $M --frontend-port $FP --backend-port $BP > "$W/logs/$L.log" 2>&1 &
echo $! > "$W/pids/$L.reflex.pid"
echo "started $L: venv=$V mode=$M app=$APP FE=$FP BE=$BP proxy=$PX reflex_pid=$(cat $W/pids/$L.reflex.pid) redis=${REDIS:-no}"
