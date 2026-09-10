#!/bin/bash
# repro_gwt_disk.sh <venv> <appdir> <bp> <label>
# Backend var named `_get_was_touched` (HP_GWT=1) vs the disk state manager: send one event, idle past the 2 s write
# debounce, look for "Error processing write queue" / "'int' object is not callable" in the server log, then stop.
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
A=$SB/apps/event_hotpath
LOGDIR=${LOGDIR:-logs3}
venv=$1; appdir=$2; bp=$3; label=$4
export REFLEX_TELEMETRY_ENABLED=false HP_GWT=1
cd $A/$appdir || exit 1
rm -f .web/nocompile
log=$A/$LOGDIR/gwt_disk_$label.log
setsid nohup $SB/envs/$venv/bin/reflex run --backend-only --backend-port $bp --loglevel debug > $log 2>&1 &
for i in $(seq 1 120); do curl -s --noproxy '*' -o /dev/null http://localhost:$bp/ping && break; sleep 1; done; sleep 2
pid=$(pgrep -f "reflex run --backend-only --backend-port $bp" | sort -n | head -1); pgid=$(ps -o pgid= -p $pid | tr -d ' ')
echo "### gwt_disk $label ($venv): one bump_hidden event, then idle 7 s"
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 timeout 60 $SB/envs/driver/bin/python $A/scripts/socket_probe.py http://localhost:$bp \
  "reflex___state____state.hotpath_app___hotpath_app____backend_state.bump_hidden" 7 $A/$LOGDIR/gwt_disk_${label}_probe.json 2>&1 | grep -E "delta\[.*backend_state|ping" | cut -c1-160
echo "periodic-flush errors while running: $(grep -c 'Error processing write queue' $log)"
grep -m2 -E "Error processing write queue|StateManagerDisk" $log | cut -c1-220
kill -TERM -- -$pgid 2>/dev/null; sleep 3; kill -KILL -- -$pgid 2>/dev/null
echo "shutdown-flush TypeError: $(grep -c "'int' object is not callable" $log)"; rm -f .web/nocompile
echo "### gwt_disk $label done"
