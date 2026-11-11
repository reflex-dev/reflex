#!/usr/bin/env bash
# start|stop a single-port prod app: app.sh start <venv> <label> <P> [ENV=VAL...] [-- extra reflex args] ; app.sh stop <label>
set -u
SB=/tmp/claude-0/-home-user/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/apps/fix022
if [ $1 = stop ]; then pg=$(cat $SB/logs/$2.pid); kill -INT -- -$pg 2>/dev/null; sleep 4; kill -9 -- -$pg 2>/dev/null; exit 0; fi
venv=$2 label=$3 P=$4; shift 4
envs=(); while [ $# -gt 0 ] && [ "$1" != "--" ]; do envs+=("$1"); shift; done; [ $# -gt 0 ] && shift
curl --noproxy '*' -s -m 1 localhost:$P >/dev/null && { echo "PORT $P BUSY"; exit 3; }
R=$SB/run/$venv/$label; rm -rf $R; mkdir -p $R; cp -a $SB/src/fapp/. $R/; cd $R
export REFLEX_TELEMETRY_ENABLED=false PATH=$SB/envs/$venv/bin:$PATH
( [ ${#envs[@]} -gt 0 ] && export "${envs[@]}"; setsid reflex run --env prod --frontend-port $P --backend-port $P "$@" > $SB/logs/$label.log 2>&1 & echo $! > $SB/logs/$label.pid )
for i in $(seq 200); do [ "$(curl --noproxy '*' -s -o /dev/null -w '%{http_code}' -m 2 localhost:$P/ping)" = 200 ] && break; sleep 2; done
curl --noproxy '*' -s -o /dev/null -w "ready $label /ping -> %{http_code}\n" localhost:$P/ping
