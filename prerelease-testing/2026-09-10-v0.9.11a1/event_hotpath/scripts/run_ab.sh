#!/bin/bash
# run_ab.sh <rounds> <variant>...   variant = venv:appdir:label   (e.g. smoke:hotpath_app:new311 base0910:hotpath_app_base:old311)
# For each round, for each variant: start `reflex run --backend-only` (dev mode, granian, 1 worker) on port 8180,
# wait for /ping, run ONE bench round (serial 2000 / 20x100 concurrent / pipelined 2000), stop the server.
# Interleaving variants per round cancels slow drift in machine load (other agents share this box).
# Output: logs3/ab_<label>_r<round>.json/.out and logs3/ab_<label>_r<round>.server.log
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
A=$SB/apps/event_hotpath
BP=8180
rounds=$1; shift
export REFLEX_TELEMETRY_ENABLED=false
for r in $(seq 1 $rounds); do
  for v in "$@"; do
    venv=${v%%:*}; rest=${v#*:}; appdir=${rest%%:*}; label=${rest#*:}
    names=$A/logs/names_smoke.json
    cd $A/$appdir || exit 1
    rm -f .web/nocompile
    setsid nohup $SB/envs/$venv/bin/reflex run --backend-only --backend-port $BP --loglevel info > $A/logs3/ab_${label}_r$r.server.log 2>&1 &
    for i in $(seq 1 120); do curl -s --noproxy '*' -o /dev/null http://localhost:$BP/ping && break; sleep 1; done
    sleep 1.5
    pid=$(pgrep -f "reflex run --backend-only --backend-port $BP" | sort -n | head -1)
    pgid=$(ps -o pgid= -p $pid | tr -d ' ')
    echo "=== round $r $label ($venv/$appdir) pid=$pid pgid=$pgid load=$(cut -d' ' -f1 /proc/loadavg) $(date +%T)"
    NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 timeout 600 $SB/envs/driver/bin/python $A/scripts/bench_socketio.py \
      --url http://localhost:$BP --names $names --server-pid $pid --out $A/logs3/ab_${label}_r$r.json --label ${label}_r$r \
      --serial 2000 --clients 20 --per-client 100 --pipelined 2000 --rounds 1 2>&1 | tee $A/logs3/ab_${label}_r$r.out | cut -c1-260
    kill -TERM -- -$pgid 2>/dev/null; sleep 2; kill -KILL -- -$pgid 2>/dev/null
    for i in $(seq 1 20); do curl -s --noproxy '*' -o /dev/null http://localhost:$BP/ping || break; sleep 0.5; done
    grep -i -E 'traceback|error|warn|destroyed|eager' $A/logs3/ab_${label}_r$r.server.log | grep -v -i -E 'sitemap|redis_lock_warning' | head -3
  done
done
echo "AB DONE $(date +%T)"
