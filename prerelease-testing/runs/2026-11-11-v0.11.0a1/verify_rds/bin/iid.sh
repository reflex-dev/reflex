#!/bin/bash
# Probe per-worker StateManagerRedis._instance_id vs RedisTokenManager.instance_id.
# Usage: iid.sh <venv> <out.jsonl> [start_method]   (prod on 3720, redis 8733, 4 workers)
. /tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/apps/verify_rds/bin/lib.sh
v=$1; OUT=$2; SM=${3:-default}; P=3720; RP=8733
redis-cli -p $RP ping >/dev/null 2>&1 || redis_up $RP
app=$W/run/lock-$v; rm -rf $app/lockapp; cp -r $W/src/lockapp/lockapp $app/
tag=iid-$v-$SM; log=$W/logs/$tag.log
( [ $SM != default ] && export REFLEX_BACKEND_START_METHOD=$SM; REFLEX_OPLOCK_ENABLED=true REFLEX_REDIS_URL=redis://localhost:$RP REFLEX_API_URL=http://localhost:$P GRANIAN_WORKERS=4 \
  start_app iid $v $app $P $P $log --env prod >/dev/null )
wait_up http://localhost:$P/ 400 >/dev/null || { echo "{\"label\":\"$tag\",\"error\":\"not up\"}" >> $OUT; stop_app iid; exit 1; }
sleep 3
for i in $(seq 60); do curl -s --noproxy '*' -H 'Connection: close' localhost:$P/api/iid; echo; done | sort -u > $W/logs/$tag.txt
echo "{\"label\":\"$tag\",\"distinct_pids\":$(cut -d, -f1 $W/logs/$tag.txt | sort -u | wc -l),\"distinct_state_manager_ids\":$(grep -o '"state_manager_instance_id": *"[^"]*"' $W/logs/$tag.txt | sort -u | wc -l),\"distinct_token_manager_ids\":$(grep -o '"token_manager_instance_id": *"[^"]*"' $W/logs/$tag.txt | sort -u | wc -l)}" >> $OUT
stop_app iid >/dev/null
