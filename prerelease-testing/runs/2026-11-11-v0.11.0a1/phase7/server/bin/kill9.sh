#!/bin/bash
# kill9.sh <venv> <workers> <out.jsonl> <label> [ENV=VAL...]: FINDING-033 repro (redis_runtime/bin/kill9.sh, verify_rds/bin/kill9.sh):
# single-port prod on 3346 with redis, connect a socket.io client, kill -9 the worker serving it mid-event, then: is the server
# still up 10 s later, which worker pids serve /api/pid, does a fresh client's event work, and does the same token resume (FINDING-032).
. /tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/p7/work/net/bin/lib.sh
v=$1 wk=$2 OUT=$3 label=$4; shift 4; P=3346; TOK=$W/run/k9-$label.tok
chkport $P || exit 3; redis_up || exit 1; redis-cli -p $RP flushall >/dev/null
app=$W/run/$v/lockapp; mkdir -p $app; cp -a $W/src/lockapp/. $app/; log=$W/logs/k9-$label.log
start k9 $v $app $log REFLEX_REDIS_URL=redis://localhost:$RP REFLEX_API_URL=http://localhost:$P GRANIAN_WORKERS=$wk "$@" -- --env prod --frontend-port $P --backend-port $P >/dev/null
wait_up http://localhost:$P/ 400 >/dev/null || { echo "NOT UP"; tail -15 $log; stop k9 >/dev/null; exit 1; }
sleep 2
pids_before=$(for i in $(seq 30); do curl -s --noproxy '*' -H 'Connection: close' localhost:$P/api/pid; echo; done | grep -o '[0-9]\+' | sort -u | tr '\n' ' ')
(cd $W && $SD $W/bin/kill9.py http://localhost:$P $RP $OUT "$label" kill $TOK) | cut -c1-300
alive=""; for i in $(seq 40); do c=$(curl -s --noproxy '*' -m1 -o /dev/null -w '%{http_code}' localhost:$P/ping); alive="$alive${c:0:1}"; sleep 0.25; done
pids_after=$(for i in $(seq 30); do curl -s --noproxy '*' -m 2 -H 'Connection: close' localhost:$P/api/pid; echo; done | grep -o '[0-9]\+' | sort -u | tr '\n' ' ')
echo "label=$label pids_before=[$pids_before] pids_after=[$pids_after] ping_every_250ms_after_kill=$alive"
if curl -s --noproxy '*' -m1 -o /dev/null localhost:$P/ping; then
  (cd $W && $SD $W/bin/load.py http://localhost:$P --clients 4 --events 20 --mode seq --label "$label|fresh-clients-after-kill" --out $OUT) | python3 -c 'import json,sys; d=json.loads(sys.stdin.read()); print("fresh clients after kill: ok", d["ok"], "/", d["of"], "sock_pids", d["sock_pids"], "exc", d["exceptions"][:1])'
  (cd $W && $SD $W/bin/kill9.py http://localhost:$P $RP $OUT "$label" resume $TOK) | python3 -c 'import json,sys; d=json.loads(sys.stdin.read()); print("same-token resume:", {k: d[k] for k in ("connect_s","first_incr_s","count")}, "new_token" if any(e[1]=="new_token" for e in d["log"]) else "kept token")'
fi
echo "server log tail:"; grep -v '^\s*$' $log | tail -6 | sed 's/^/  /'
stop k9
