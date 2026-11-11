#!/bin/bash
# Variants of kill9.sh to separate granian's choice from reflex's.
# Usage: kill9b.sh <venv> <workers> <out.jsonl> <mode>
#   mode=delrec  : kill -9 worker, server stops, DEL the stale token_manager_socket_record_<tok>, restart, resume same token
#   mode=respawn : PYTHONPATH sitecustomize sets granian respawn_failed_workers=True; kill -9 worker; no restart; resume same token
#   mode=clean   : no kill: SIGTERM the server while the socket is connected, restart, resume same token
. /tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/apps/verify_rds/bin/lib.sh
v=$1; wk=$2; OUT=$3; mode=$4; P=3721; RP=8733; D=$SB/envs/vrds-drv/bin/python; app=$W/run/lock-$v; TOK=$W/run/k9b.tok
redis-cli -p $RP ping >/dev/null 2>&1 || redis_up $RP
redis-cli -p $RP flushall >/dev/null
[ $mode = respawn ] && export PYTHONPATH=$W/respawn_hook
run() { REFLEX_REDIS_URL=redis://localhost:$RP REFLEX_API_URL=http://localhost:$P GRANIAN_WORKERS=$wk start_app k9b $v $app $P $P $W/logs/k9b-$v-$mode-$1.log --env prod >/dev/null; wait_up http://localhost:$P/ 300 >/dev/null; }
run a; sleep 2
if [ $mode = clean ]; then
  $D $W/bin/kill9.py http://localhost:$P $RP $OUT "$v-w$wk-$mode" connect_only $TOK &
  sleep 3; stop_app k9b; wait
else
  $D $W/bin/kill9.py http://localhost:$P $RP $OUT "$v-w$wk-$mode" kill $TOK
fi
sleep 3
TK=$(cat $TOK)
echo "{\"label\":\"$v-w$wk-$mode\",\"server_alive_3s_after\":$(curl -s --noproxy '*' -m1 -o /dev/null localhost:$P && echo true || echo false),\"socket_record_exists\":$(redis-cli -p $RP exists token_manager_socket_record_$TK),\"state_keys\":$(redis-cli -p $RP --scan --pattern "$TK*" | wc -l),\"server_log_tail\":\"$(tail -3 $W/logs/k9b-$v-$mode-a.log | tr '\n"' ' _')\"}" >> $OUT
[ $mode = delrec ] && redis-cli -p $RP del token_manager_socket_record_$TK >/dev/null
if [ $mode != respawn ]; then stop_app k9b >/dev/null; run b; fi
$D $W/bin/kill9.py http://localhost:$P $RP $OUT "$v-w$wk-$mode" resume $TOK
stop_app k9b
