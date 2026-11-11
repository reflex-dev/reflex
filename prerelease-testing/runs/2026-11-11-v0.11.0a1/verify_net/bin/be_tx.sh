#!/usr/bin/env bash
# backend-only prod with an api_transformer variant: be_tx.sh <venv> <VN_TX> <BP>
set -u
SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad; W=$SB/apps/verify_net
venv=$1 tx=$2 BP=$3
curl --noproxy '*' -s -m1 localhost:$BP >/dev/null && { echo BUSY; exit 3; }
D=$W/run/$venv/lp; mkdir -p $D; cp -a $W/src/vapp/. $D/; cd $D
export REFLEX_TELEMETRY_ENABLED=false VN_VENV=$venv VN_TX=$tx
( setsid $SB/envs/$venv/bin/reflex run --env prod --backend-only --backend-port $BP > $W/logs/be_${venv}_$tx.log 2>&1 & )
for i in $(seq 60); do curl --noproxy '*' -s -m1 localhost:$BP/ping >/dev/null && break; sleep 2; done
echo "== $venv $tx: /api/greeting -> $(curl --noproxy '*' -s localhost:$BP/api/greeting)"
pg=$(ps -eo pgid,cmd | grep "envs/$venv/bin/reflex run --env prod --backend-only --backend-port $BP" | grep -v grep | awk '{print $1}' | head -1)
kill -INT -- -$pg; sleep 4; kill -9 -- -$pg 2>/dev/null
grep -v -E 'DeprecationWarning|Request: |SitemapPlugin' $W/logs/be_${venv}_$tx.log | grep -i -E 'lifespan|unsupported|VN_MARK|KeyError' | cut -c1-200
