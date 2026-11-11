#!/usr/bin/env bash
# start|stop a single-port prod server: single.sh start <venv> <label> <P> [ENV=VAL...] ; single.sh stop <label>
set -u
SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad; W=$SB/apps/verify_net
if [ $1 = stop ]; then pg=$(cat $W/logs/$2.pid); kill -INT -- -$pg 2>/dev/null; sleep 4; kill -9 -- -$pg 2>/dev/null; exit 0; fi
venv=$2 label=$3 P=$4; shift 4
curl --noproxy '*' -s -m 1 localhost:$P >/dev/null && { echo "PORT $P BUSY"; exit 3; }
R=$W/run/$venv/single; mkdir -p $R; cp -a $W/src/vapp/. $R/; cd $R
export REFLEX_TELEMETRY_ENABLED=false VN_VENV=$venv PATH=$SB/envs/$venv/bin:$PATH
( [ $# -gt 0 ] && export "$@"; setsid reflex run --env prod --frontend-port $P --backend-port $P > $W/logs/$label.log 2>&1 & echo $! > $W/logs/$label.pid )
for i in $(seq 200); do [ "$(curl --noproxy '*' -s -o /dev/null -w '%{http_code}' -m 2 localhost:$P/)" = 200 ] && break; sleep 2; done
curl --noproxy '*' -s -o /dev/null -w "ready $label / -> %{http_code}\n" localhost:$P/
