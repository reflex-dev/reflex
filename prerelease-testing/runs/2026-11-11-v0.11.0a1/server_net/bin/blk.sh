#!/usr/bin/env bash
# Blocking-monitor knob run: blk.sh <label> <dev|prod> [ENV=VAL ...]; clicks block_sync, block_async, cpu_bg; counts warnings.
set -u
SB=${SB:?}; W=${W:-$SB/apps/server_net}
label=$1 mode=$2; shift 2
args=(--frontend-port 3354 --backend-port 8354); url=http://localhost:3354/
[ $mode = prod ] && args=(--env prod --frontend-port 3354 --backend-port 3354)
( [ $# -gt 0 ] && export "$@"; $W/bin/srv.sh start $label server_net-main netapp "${args[@]}" >/dev/null )
if LABEL=$label $W/bin/srv.sh wait $url 300 >/dev/null; then
  [ $mode = dev ] && $W/bin/srv.sh wait http://localhost:8354/ping 60 >/dev/null
  sleep 3
  (cd $SB; NA_BLOCK_BUTTONS=block_sync,block_async,cpu_bg NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 timeout 300 $SB/envs/driver/bin/python $W/drivers/drv.py $url block $W/res/$label.json 2>&1 | head -1)
  sleep 2
fi
$W/bin/srv.sh stop $label >/dev/null
echo "$label ($mode $*): blocking-warnings=$(grep -c 'is blocking the event loop' $W/logs/$label.log) totals=$(grep -A0 'in total' $W/logs/$label.log | sed 's/Warning: Event handler //' | tr '\n' ';')"
grep -i -E "threshold|ConfigError|invalid|error" $W/logs/$label.log | grep -v "is blocking" | head -4 | sed 's/^/  log: /'
