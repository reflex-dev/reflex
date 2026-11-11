#!/bin/bash
# Usage: cancel.sh <venv> [oplock 0|1]   prod + Redis 8733, 1 worker, port 3722; runs drive_cancel.py (Chromium)
. /tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/apps/verify_rds/bin/lib.sh
v=$1; op=${2:-0}; P=3722; RP=8733
redis-cli -p $RP ping >/dev/null 2>&1 || redis_up $RP
redis-cli -p $RP flushall >/dev/null
app=$W/run/lock-$v; rm -rf $app/lockapp; cp -r $W/src/lockapp/lockapp $app/
tag=cx-$v-op$op; log=$W/logs/$tag.log
REFLEX_OPLOCK_ENABLED=$([ $op = 1 ] && echo true || echo false) REFLEX_REDIS_URL=redis://localhost:$RP REFLEX_API_URL=http://localhost:$P GRANIAN_WORKERS=1 \
  start_app cx $v $app $P $P $log --env prod >/dev/null
wait_up http://localhost:$P/ 400 >/dev/null || { echo "not up"; stop_app cx; exit 1; }
sleep 2
env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 timeout 400 $SB/envs/driver/bin/python $W/bin/drive_cancel.py http://localhost:$P $W/logs/$tag.json $W/shots/$tag
stop_app cx
