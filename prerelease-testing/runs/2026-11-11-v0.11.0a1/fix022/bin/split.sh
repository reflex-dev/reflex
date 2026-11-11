#!/usr/bin/env bash
# split.sh <venv> <label> <FP> <BP> [backend ENV=VAL ...]: docs' split deployment, Chromium on the frontend
set -u
SB=/tmp/claude-0/-home-user/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/apps/fix022
venv=$1 label=$2 FP=$3 BP=$4; shift 4
R=$SB/run/$venv/$label; rm -rf $R; mkdir -p $R; cp -a $SB/src/fapp/. $R/; cd $R
export REFLEX_TELEMETRY_ENABLED=false PATH=$SB/envs/$venv/bin:$PATH
( [ $# -gt 0 ] && export "$@"; setsid reflex run --env prod --backend-only --backend-port $BP > $SB/logs/${label}_be.log 2>&1 & echo $! > $SB/logs/${label}_be.pid )
for i in $(seq 120); do curl --noproxy '*' -s -m 1 localhost:$BP/ping >/dev/null && break; sleep 2; done
( export REFLEX_API_URL=http://localhost:$BP; setsid reflex run --env prod --frontend-only --frontend-port $FP > $SB/logs/${label}_fe.log 2>&1 & echo $! > $SB/logs/${label}_fe.pid )
for i in $(seq 200); do [ "$(curl --noproxy '*' -s -o /dev/null -w '%{http_code}' -m 2 localhost:$FP/)" = 200 ] && break; sleep 2; done
$SB/bin/browse.sh $label http://localhost:$FP/
for s in fe be; do kill -INT -- -$(cat $SB/logs/${label}_$s.pid) 2>/dev/null; done; sleep 4
for s in fe be; do kill -9 -- -$(cat $SB/logs/${label}_$s.pid) 2>/dev/null; done
grep -h -A3 "Rejected an event" $SB/logs/${label}_be.log | head -6 | sed 's/^/  backend log: /'
