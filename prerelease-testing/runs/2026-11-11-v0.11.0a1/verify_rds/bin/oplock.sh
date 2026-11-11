#!/bin/bash
# Usage: oplock.sh <venv> <out.jsonl> <patch 0|1> "<api-conc list>" [runs]   (prod on 3720, redis 8733, oplock on, 2 workers)
. /tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/apps/verify_rds/bin/lib.sh
v=$1; OUT=$2; patch=$3; CONCS=$4; RUNS=${5:-6}; P=3720; RP=8733; D=$SB/envs/vrds-drv/bin/python; L=$W/bin/load.py
redis-cli -p $RP ping >/dev/null 2>&1 || redis_up $RP
app=$W/run/lock-$v; rm -rf $app/lockapp; cp -r $W/src/lockapp/lockapp $app/ 2>/dev/null || cp -r $W/src/lockapp $app
redis-cli -p $RP flushall >/dev/null
tag=op-$v-p$patch${START_METHOD:+-$START_METHOD}; log=$W/logs/$tag.log
[ -n "$START_METHOD" ] && export REFLEX_BACKEND_START_METHOD=$START_METHOD
RDS_PATCH_SREM=$patch REFLEX_OPLOCK_ENABLED=true REFLEX_REDIS_URL=redis://localhost:$RP REFLEX_API_URL=http://localhost:$P GRANIAN_WORKERS=2 \
  start_app op $v $app $P $P $log --env prod $EXTRA_ARGS >/dev/null
wait_up http://localhost:$P/ 400 >/dev/null || { echo "{\"label\":\"$tag\",\"error\":\"not up\"}" >> $OUT; stop_app op; exit 1; }
sleep 2
for c in $CONCS; do for i in $(seq $RUNS); do
  $D $L http://localhost:$P --clients 1 --events 300 --mode pipe --api 100 --api-conc $c --label "$tag|conc$c|$i" --out $OUT >/dev/null
done; done
if [ "${SPOT:-0}" = 1 ]; then
  $D $L http://localhost:$P --clients 8 --events 50 --mode pipe --bg 40 --api 40 --label "$tag|spot|pipe8x50+bg40+api40" --out $OUT >/dev/null
  $D $L http://localhost:$P --clients 1 --events 300 --mode pipe --bg 200 --api 200 --label "$tag|spot|pipe1x300+bg200+api200" --out $OUT >/dev/null
  $D $L http://localhost:$P --clients 4 --events 50 --mode seq --bg 100 --api 50 --label "$tag|spot|seq4x50+bg100+api50" --out $OUT >/dev/null
fi
echo "{\"label\":\"$tag|stop\",\"stop\":\"$(stop_app op)\",\"patch_lines\":$(grep -c 'RDS_PATCH_SREM applied' $log),\"log_err\":$(grep -c -i -E 'traceback|error|expired' $log)}" >> $OUT
