#!/bin/bash
# Load/correctness matrix. Usage: matrix.sh <out.jsonl> "<venv...>" "<oplock 0 1>" "<workers 1 2 4>"
. /tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/apps/redis_runtime/bin/lib.sh
OUT=$1; VENVS=$2; OPS=${3:-"0 1"}; WKS=${4:-"1 2 4"}; P=3220; RP=8236
D=$SB/envs/redis_runtime-drv/bin/python; L=$W/bin/load.py
redis-cli -p $RP ping >/dev/null 2>&1 || redis_up $RP
for v in $VENVS; do
  app=$W/run/lock-$v; [ -d $app ] || cp -r $W/src/lockapp $app
  for op in $OPS; do for wk in $WKS; do
    tag=m-$v-op$op-w$wk; log=$W/logs/$tag.log
    redis-cli -p $RP flushall >/dev/null
    REFLEX_OPLOCK_ENABLED=$([ $op = 1 ] && echo true || echo false) REFLEX_REDIS_URL=redis://localhost:$RP REFLEX_API_URL=http://localhost:$P GRANIAN_WORKERS=$wk \
      start_app mx $v $app $P $P $log --env prod >/dev/null
    wait_up http://localhost:$P/ 400 >/dev/null || { echo "{\"label\":\"$tag\",\"error\":\"not up\"}" >> $OUT; stop_app mx; continue; }
    sleep 2
    $D $L http://localhost:$P --clients 8 --events 50 --mode seq --label "$tag|seq8x50" --out $OUT >/dev/null
    $D $L http://localhost:$P --clients 4 --events 50 --mode seq --bg 100 --api 50 --label "$tag|seq4x50+bg100+api50" --out $OUT >/dev/null
    $D $L http://localhost:$P --clients 8 --events 50 --mode pipe --bg 40 --api 40 --label "$tag|pipe8x50+bg40+api40" --out $OUT >/dev/null
    $D $L http://localhost:$P --clients 1 --events 300 --mode pipe --bg 200 --api 200 --label "$tag|pipe1x300+bg200+api200" --out $OUT >/dev/null
    echo "{\"label\":\"$tag|stop\",\"stop\":\"$(stop_app mx)\",\"log_err\":$(grep -c -i -E 'traceback|error|warning|expired' $log)}" >> $OUT
  done; done
done
