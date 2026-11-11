#!/usr/bin/env bash
# Documented split deployment (docs/hosting/self-hosting.md @ v0.11.0a1 L68-71), literally:
#   reflex run --env prod --backend-only --backend-port BP
#   REFLEX_API_URL=http://localhost:BP reflex run --env prod --frontend-only --frontend-port FP
# usage: split.sh <venv> <label> <FP> <BP> [backend ENV=VAL ...]
set -u
SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad; W=$SB/apps/verify_net
venv=$1 label=$2 FP=$3 BP=$4; shift 4
for p in $FP $BP; do curl --noproxy '*' -s -m 1 localhost:$p >/dev/null && { echo "PORT $p BUSY"; exit 3; }; done
R=$W/run/$venv/vapp; mkdir -p $R; cp -a $W/src/vapp/. $R/
cd $R
export REFLEX_TELEMETRY_ENABLED=false VN_VENV=$venv PATH=$SB/envs/$venv/bin:$PATH
( [ $# -gt 0 ] && export "$@"; setsid reflex run --env prod --backend-only --backend-port $BP > $W/logs/${label}_be.log 2>&1 & echo $! > $W/logs/${label}_be.pid )
for i in $(seq 120); do curl --noproxy '*' -s -m 1 localhost:$BP/ping >/dev/null && break; sleep 2; done
( export REFLEX_API_URL=http://localhost:$BP; setsid reflex run --env prod --frontend-only --frontend-port $FP > $W/logs/${label}_fe.log 2>&1 & echo $! > $W/logs/${label}_fe.pid )
for i in $(seq 200); do [ "$(curl --noproxy '*' -s -o /dev/null -w '%{http_code}' -m 2 localhost:$FP/)" = 200 ] && break; sleep 2; done
echo "##### $label ($venv) backend env: $*"
(cd $SB && NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 timeout 120 $SB/envs/driver/bin/python $W/bin/drv.py http://localhost:$FP/ $W/res/$label.json $W/res/$label.png)
for s in fe be; do pg=$(cat $W/logs/${label}_$s.pid); kill -INT -- -$pg 2>/dev/null; done; sleep 4
for s in fe be; do pg=$(cat $W/logs/${label}_$s.pid); kill -9 -- -$pg 2>/dev/null; done
grep -h -i "accepted origin" $W/logs/${label}_be.log | head -3 | sed 's/^/  backend log: /'
