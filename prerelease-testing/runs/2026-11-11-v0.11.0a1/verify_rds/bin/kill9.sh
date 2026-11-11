#!/bin/bash
# kill -9 one granian worker mid-event (whole server stops), restart it at once, time the first event for the same token.
# Usage: kill9.sh <venv> <workers> <out.jsonl>    (prod on 3221, redis 8237)
. /tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/apps/verify_rds/bin/lib.sh
v=$1; wk=$2; OUT=$3; P=3721; RP=8733; D=$SB/envs/vrds-drv/bin/python; app=$W/run/lock-$v; TOK=$W/run/k9.tok
redis-cli -p $RP ping >/dev/null 2>&1 || redis_up $RP
run() { REFLEX_REDIS_URL=redis://localhost:$RP REFLEX_API_URL=http://localhost:$P GRANIAN_WORKERS=$wk start_app k9 $v $app $P $P $W/logs/k9-$v-$1.log --env prod >/dev/null; wait_up http://localhost:$P/ 300 >/dev/null; }
run a; sleep 2
$D $W/bin/kill9.py http://localhost:$P $RP $OUT "$v-w$wk" kill $TOK
for i in $(seq 1 40); do curl -s --noproxy '*' -m1 -o /dev/null localhost:$P || break; sleep 0.25; done
echo "server down after kill: $(tail -2 $W/logs/k9-$v-a.log | tr '\n' ' ')"
stop_app k9 >/dev/null
run b
$D $W/bin/kill9.py http://localhost:$P $RP $OUT "$v-w$wk" resume $TOK
stop_app k9
