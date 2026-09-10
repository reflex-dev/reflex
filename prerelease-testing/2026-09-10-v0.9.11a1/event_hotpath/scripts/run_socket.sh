#!/bin/bash
# run_socket.sh <venv> <appdir> <label>  -- backend-only server on 8189; runs socket_slow_test.py + socket_malformed_test.py
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
A=$SB/apps/event_hotpath
LOGDIR=${LOGDIR:-logs3}
venv=$1; appdir=$2; label=$3; BP=8189
export REFLEX_TELEMETRY_ENABLED=false
cd $A/$appdir || exit 1
rm -f .web/nocompile
setsid nohup $SB/envs/$venv/bin/reflex run --backend-only --backend-port $BP --loglevel info > $A/$LOGDIR/socket_$label.server.log 2>&1 &
for i in $(seq 1 120); do curl -s --noproxy '*' -o /dev/null http://localhost:$BP/ping && break; sleep 1; done
sleep 1.5
pid=$(pgrep -f "reflex run --backend-only --backend-port $BP" | sort -n | head -1); pgid=$(ps -o pgid= -p $pid | tr -d ' ')
echo "=== socket tests $label ($venv/$appdir) pid=$pid"
cd $A/scripts
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 timeout 120 $SB/envs/driver/bin/python socket_slow_test.py --url http://localhost:$BP --names $A/logs/names_smoke.json --out $A/$LOGDIR/socket_slow_$label.json --label $label 2>&1 | cut -c1-300
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 timeout 180 $SB/envs/driver/bin/python socket_malformed_test.py --url http://localhost:$BP --names $A/logs/names_smoke.json --out $A/$LOGDIR/socket_malformed_$label.json --label $label 2>&1 | grep -E "FAIL|DONE|burst|ping_after" | cut -c1-300
kill -TERM -- -$pgid 2>/dev/null; sleep 2; kill -KILL -- -$pgid 2>/dev/null
echo "--- server log scan:"; grep -n -i -E 'traceback|warn|destroyed|eager|never awaited|deserializ' $A/$LOGDIR/socket_$label.server.log | grep -v -i -E 'sitemap|redis_lock_warning|intentional' | cut -c1-200 | head -12
grep -c "intentional" $A/$LOGDIR/socket_$label.server.log | sed 's/^/intentional-boom tracebacks: /'
