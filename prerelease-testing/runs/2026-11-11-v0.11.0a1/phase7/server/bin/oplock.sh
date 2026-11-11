#!/bin/bash
# oplock.sh <venv> <workers> <out.jsonl> "<api-conc list>" [runs]: FINDING-030 repro (verify_rds/bin/oplock.sh + iid.sh):
# single-port prod on 3345, redis 6391, REFLEX_OPLOCK_ENABLED=true, GRANIAN_WORKERS=<workers>; worker-id probe, then per conc
# <runs> x (1 client, 300 pipelined incr events + 100 POST /api/bump via app.modify_state at that concurrency). Stall = api wait > 500 ms.
. /tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/p7/work/net/bin/lib.sh
v=$1 wk=$2 OUT=$3 CONCS=$4 RUNS=${5:-6}; P=3345
chkport $P || exit 3; redis_up || { echo no redis; exit 1; }; redis-cli -p $RP flushall >/dev/null
tag=op-$v-w$wk${START_METHOD:+-$START_METHOD}; log=$W/logs/$tag.log; app=$W/run/$v/lockapp; mkdir -p $app; cp -a $W/src/lockapp/. $app/
start $tag $v $app $log REFLEX_OPLOCK_ENABLED=true REFLEX_REDIS_URL=redis://localhost:$RP REFLEX_API_URL=http://localhost:$P GRANIAN_WORKERS=$wk ${START_METHOD:+REFLEX_BACKEND_START_METHOD=$START_METHOD} -- --env prod --frontend-port $P --backend-port $P >/dev/null
wait_up http://localhost:$P/ 400 >/dev/null || { echo "{\"label\":\"$tag\",\"error\":\"not up\"}" >> $OUT; tail $log; stop $tag; exit 1; }
sleep 3
for i in $(seq 80); do curl -s --noproxy '*' -H 'Connection: close' localhost:$P/api/iid; echo; done | sort -u > $W/res/$tag.iid.txt
echo "{\"label\":\"$tag|iid\",\"distinct_pids\":$(grep -o '"pid":[0-9]*' $W/res/$tag.iid.txt | sort -u | wc -l),\"distinct_state_manager_ids\":$(grep -o '"state_manager_instance_id":"[^"]*"' $W/res/$tag.iid.txt | sort -u | wc -l),\"distinct_token_manager_ids\":$(grep -o '"token_manager_instance_id":"[^"]*"' $W/res/$tag.iid.txt | sort -u | wc -l)}" | tee -a $OUT
for c in $CONCS; do for i in $(seq $RUNS); do
  (cd $W && $SD $W/bin/load.py http://localhost:$P --clients 1 --events 300 --mode pipe --api 100 --api-conc $c --label "$tag|conc$c|$i" --out $OUT >/dev/null)
done; done
echo "{\"label\":\"$tag|stop\",\"stop\":\"$(stop $tag)\",\"log_err\":$(grep -c -i -E 'traceback|error|expired' $log),\"slow_bumps\":$(grep -c RDS_SLOW_BUMP $log)}" | tee -a $OUT
