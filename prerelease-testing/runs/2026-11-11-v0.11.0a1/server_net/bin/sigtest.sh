#!/usr/bin/env bash
# Start netapp, wait for it, send a signal, report exit time/code, shutdown marks, leftovers.
#   sigtest.sh <label> <venv> <mode dev|prod|prod-be> <sig INT|TERM> <target group|pid> [fp] [bp]
# extra env (NA_TX, ...) is passed through.  Prints a one-line verdict + marks.
set -u
SB=${SB:?}; W=${W:-$SB/apps/server_net}
label=$1 venv=$2 mode=$3 sig=$4 target=$5 fp=${6:-3342} bp=${7:-8342}
log=$W/logs/$label.log; marks=$W/logs/$label.jsonl; : > "$marks"
case $mode in
  dev) args=(--frontend-port $fp --backend-port $bp); url=http://localhost:$fp/; burl=http://localhost:$bp/ping ;;
  prod) args=(--env prod --frontend-port $fp --backend-port $fp); url=http://localhost:$fp/; burl=http://localhost:$fp/ping ;;
  prod-be) args=(--env prod --backend-only --backend-port $bp); url=http://localhost:$bp/ping; burl=$url ;;
  dev-be) args=(--backend-only --backend-port $bp); url=http://localhost:$bp/ping; burl=$url ;;
esac
for p in $fp $bp; do curl --noproxy '*' -s -m 2 localhost:$p >/dev/null && { echo "PORT $p BUSY"; exit 3; }; done
NA_LOG=$marks $W/bin/srv.sh start "$label" "$venv" netapp ${JSON:+--json} "${args[@]}" >/dev/null
LABEL=$label $W/bin/srv.sh wait "$url" 400 >/dev/null || { echo "$label: never came up"; tail -20 $log; $W/bin/srv.sh stop $label; exit 1; }
[ "$mode" = dev ] && $W/bin/srv.sh wait "$burl" 120 >/dev/null
sleep ${SETTLE:-3}
pid=$(cat $W/logs/$label.pid)
tree_before=$(ps -o pid=,comm= --ppid $pid; ps -eo pid=,pgid=,comm= | awk -v g=$pid '$2==g' | wc -l)
t0=$(date +%s.%N)
if [ "$target" = group ]; then kill -$sig -- -$pid; else kill -$sig $pid; fi
code=
for i in $(seq 1 ${MAXWAIT:-80}); do
  if ! kill -0 $pid 2>/dev/null; then break; fi
  sleep 0.25
done
t1=$(date +%s.%N)
alive=$(kill -0 $pid 2>/dev/null && echo yes || echo no)
wait_s=$(echo "$t1 - $t0" | bc)
sleep 1
left=$(ps -eo pid=,pgid=,comm= | awk -v g=$pid '$2==g' | tr '\n' ';')
listen=""; for p in $fp $bp; do curl --noproxy '*' -s -m 1 localhost:$p >/dev/null && listen="$listen $p"; done
echo "$label venv=$venv mode=$mode sig=$sig->$target: top_alive=$alive after ${wait_s}s; group_left=[$left] listening=[$listen]"
echo "  marks: $(jq -r '.evt' $marks 2>/dev/null | tr '\n' ' ')"
$W/bin/srv.sh stop $label >/dev/null
