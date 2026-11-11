#!/usr/bin/env bash
# logrun.sh <venv> <label> <port> [env assignments...]: backend-only prod forkapp, 40x /api/log, count direct vs queued
# log lines per pid, 60x /api/whoami summary, then SIGTERM. Extra env (e.g. REFLEX_BACKEND_START_METHOD=spawn,
# PYTHONWARNINGS=default) is exported for the server.
set -u; : "${SB:?}"; V=$SB/apps/verify_pm1; cd "$V" || exit 2
venv=$1; label=$2; port=$3; shift 3
for kv in "$@"; do export "$kv"; done
export REFLEX_REDIS_URL=${REFLEX_REDIS_URL:-redis://localhost:8739} REFLEX_TELEMETRY_ENABLED=false
rm -f forkapp/forkapp.log forkapp/forkapp.log.q
./scripts/serve.sh start "$venv" "$V/forkapp" "$label" prod-be "$port" > /dev/null
pid=$(cat "run/$label.pid"); up=$(./scripts/serve.sh wait "http://localhost:$port/ping" 180)
echo "## $label venv=$venv port=$port env=[$*] $up"
for i in $(seq 1 40); do curl -s --noproxy '*' -o /dev/null "http://localhost:$port/api/log?m=$i"; done
sleep 1.5
echo "direct log lines: $(wc -l < forkapp/forkapp.log) (pids: $(grep -o 'pid=[0-9]*' forkapp/forkapp.log | sort | uniq -c | wc -l)); queued log lines: $(wc -l < forkapp/forkapp.log.q) (pids: $(grep -o 'pid=[0-9]*' forkapp/forkapp.log.q | sort | uniq -c | wc -l))"
echo "queued log content:"; cut -c1-120 forkapp/forkapp.log.q
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 "$SB/envs/driver/bin/python" -I scripts/sample_whoami.py "http://localhost:$port" 60 --json "out/whoami-$label.json" | tail -1
"$SB/envs/driver/bin/python" -I scripts/tree.py "$pid" --json "out/tree-$label.json" | tail -1
./scripts/serve.sh stop "$label" TERM
cp forkapp/forkapp.log "out/forkapp-$label-direct.log"; cp forkapp/forkapp.log.q "out/forkapp-$label-queued.log"
echo "log: tracebacks=$(grep -c Traceback logs/$label.log) multi-threaded-warning=$(grep -c 'multi-threaded' logs/$label.log) spawning-workers-fallback=$(grep -c 'spawning workers' logs/$label.log)"
