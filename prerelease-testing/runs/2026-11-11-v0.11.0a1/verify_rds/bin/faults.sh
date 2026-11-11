#!/bin/bash
# Usage: faults.sh <venv> <oplock 0|1> <workers> <out.jsonl> [scenarios...]   (prod on 3221, redis 8237)
. /tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/apps/verify_rds/bin/lib.sh
v=$1; op=$2; wk=$3; OUT=$4; shift 4; SC=${@:-"lost_none lost_kill_pubsub lost_config_off kill9 redis_restart sigstop"}
P=3721; RP=8733; D=$SB/envs/vrds-drv/bin/python
redis-cli -p $RP ping >/dev/null 2>&1 || redis_up $RP
app=$W/run/lock-$v; [ -d $app ] || cp -r $W/src/lockapp $app
for sc in $SC; do
  tag=f-$v-op$op-w$wk-$sc; log=$W/logs/$tag.log
  redis-cli -p $RP ping >/dev/null 2>&1 || redis_up $RP
  redis-cli -p $RP flushall >/dev/null
  REFLEX_OPLOCK_ENABLED=$([ $op = 1 ] && echo true || echo false) REFLEX_REDIS_URL=redis://localhost:$RP REFLEX_API_URL=http://localhost:$P GRANIAN_WORKERS=$wk \
    start_app fx $v $app $P $P $log --env prod >/dev/null
  wait_up http://localhost:$P/ 400 >/dev/null || { echo "{\"label\":\"$tag\",\"error\":\"not up\"}" >> $OUT; stop_app fx; continue; }
  sleep 2
  timeout 300 $D $W/bin/faults.py http://localhost:$P $RP $sc ${DOWN:+--down $DOWN} --label $tag --out $OUT --redis-pidfile $W/pids/redis-$RP.pid > /dev/null 2>$W/logs/$tag.drv.err || echo "{\"label\":\"$tag\",\"error\":\"driver rc=$? $(tail -c 300 $W/logs/$tag.drv.err | tr '\n"' ' _')\"}" >> $OUT
  echo "{\"label\":\"$tag|stop\",\"stop\":\"$(stop_app fx)\",\"log_lines\":$(grep -c -i -E 'traceback|error|expired|timeout' $log)}" >> $OUT
done
