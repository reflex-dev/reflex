#!/usr/bin/env bash
# Double Ctrl-C: dblint.sh <venv> <dev|prod> ; lifespan cleanup sleeps NA_SLOW_STOP=60 s. INT group at t0, again at t0+GAP (3 s).
set -u
SB=${SB:?}; W=${W:-$SB/apps/server_net}
venv=$1 mode=$2 label=dbl_$1_$2
marks=$W/logs/$label.jsonl; : > $marks
args=(--frontend-port 3359 --backend-port 8359); url=http://localhost:3359/
[ $mode = prod ] && args=(--env prod --frontend-port 3359 --backend-port 3359)
NA_SLOW_STOP=60 NA_LOG=$marks $W/bin/srv.sh start $label $venv netapp "${args[@]}" >/dev/null
LABEL=$label $W/bin/srv.sh wait $url 300 >/dev/null; [ $mode = dev ] && $W/bin/srv.sh wait http://localhost:8359/ping 60 >/dev/null; sleep 4
pid=$(cat $W/logs/$label.pid)
t0=$(date +%s.%N); kill -INT -- -$pid
for i in $(seq 1 ${FIRST:-12}); do kill -0 $pid 2>/dev/null || break; sleep 0.25; done
s1=$(kill -0 $pid 2>/dev/null && echo alive || echo exited)
t1=$(date +%s.%N); kill -INT -- -$pid 2>/dev/null
for i in $(seq 1 120); do kill -0 $pid 2>/dev/null || break; sleep 0.25; done
t2=$(date +%s.%N)
left=$(ps -eo pid=,pgid=,comm= | awk -v g=$pid '$2==g' | tr '\n' ';')
lis=""; for p in 3359 8359; do lsof -iTCP:$p -sTCP:LISTEN -t >/dev/null 2>&1 && lis="$lis $p"; done
echo "$venv $mode: after 1st INT (${FIRST:-12}x0.25s): $s1; after 2nd INT exit in $(echo "$t2 - $t1" | bc)s; total $(echo "$t2 - $t0" | bc)s; leftover=[$left] listening=[$lis]"
echo "  marks: $(jq -r .evt $marks | tr '\n' ' ')"
tail -4 $W/logs/$label.log | sed 's/^/  log: /'
kill -9 -- -$pid 2>/dev/null; true
