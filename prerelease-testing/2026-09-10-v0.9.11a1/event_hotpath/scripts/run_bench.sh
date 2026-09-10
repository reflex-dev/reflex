#!/bin/bash
# run_bench.sh <venv> <appdir> <backend_port> <label> [names.json]
# Starts `reflex run --backend-only` (dev mode, granian, one worker) for the given venv/app, waits for /ping,
# runs bench_socketio.py against it (serial 2000, 20x100 concurrent, pipelined 2000, 2 rounds), stops the server,
# and reports whether the run left a stale `.web/nocompile` marker behind.
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
A=$SB/apps/event_hotpath
venv=$1; appdir=$2; bp=$3; label=$4; names=${5:-$A/logs/names_smoke.json}
export REFLEX_TELEMETRY_ENABLED=false
cd $A/$appdir || exit 1
rm -f .web/nocompile
setsid nohup $SB/envs/$venv/bin/reflex run --backend-only --backend-port $bp --loglevel info > $A/logs2/bench_$label.server.log 2>&1 &
pid=$!
echo "server pid $pid"
for i in $(seq 1 90); do
  curl -s --noproxy '*' -o /dev/null http://localhost:$bp/ping && break
  sleep 1
done
sleep 2
echo "nocompile marker after backend-only start: $(ls .web/nocompile 2>/dev/null || echo absent)"
# the granian worker is a child of the reflex process; cpu_tree() in the bench sums the whole tree
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python $A/scripts/bench_socketio.py \
  --url http://localhost:$bp --names $names --server-pid $pid --out $A/logs2/bench_$label.json --label $label \
  --serial 2000 --clients 20 --per-client 100 --pipelined 2000 --rounds 2 2>&1 | tee $A/logs2/bench_$label.out
pgid=$(ps -o pgid= -p $pid | tr -d ' ')
kill -TERM -- -$pgid 2>/dev/null; sleep 3; kill -KILL -- -$pgid 2>/dev/null
echo "nocompile marker after server stop: $(ls .web/nocompile 2>/dev/null || echo absent)"
grep -i -E 'warn|error|traceback|destroyed' $A/logs2/bench_$label.server.log | grep -v -i 'sitemap\|redis_lock_warning' | head -5
echo "DONE $label"
