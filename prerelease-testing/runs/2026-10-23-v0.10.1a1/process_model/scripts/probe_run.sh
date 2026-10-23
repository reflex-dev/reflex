#!/usr/bin/env bash
# probe_run.sh <venv> <label> <mode: prod|prod-be> <port> [stop signal]  (env vars such as REFLEX_REDIS_URL,
# GRANIAN_WORKERS, REFLEX_BACKEND_START_METHOD, REFLEX_TELEMETRY_ENABLED are passed through)
# start -> wait for /ping (timed) -> tree.py -> sample_whoami.py -> stop -> log scan. Writes out/<label>.*.
set -u
: "${SB:?}"; PM=$SB/apps/process_model; cd "$PM" || exit 2
venv=$1; label=$2; mode=$3; port=$4; sig=${5:-TERM}
rm -f forkapp/forkapp.log forkapp/forkapp.log.q
t0=$(date +%s.%N)
./scripts/serve.sh start "$venv" "$PM/forkapp" "$label" "$mode" "$port" > /dev/null
pid=$(cat "run/$label.pid")
up=$(./scripts/serve.sh wait "http://localhost:$port/ping" 180)
t1=$(date +%s.%N)
if [ "$pid" ] && kill -0 "$pid" 2>/dev/null; then alive=yes; else alive=no; fi
echo "## $label venv=$venv mode=$mode port=$port pid=$pid alive=$alive $up ($(printf '%.1f' "$(echo "$t1 - $t0" | bc)")s wall)"
if [ "$alive" = yes ] && echo "$up" | grep -q "^up"; then
  sleep 1
  "$SB/envs/driver/bin/python" -I scripts/tree.py "$pid" --json "out/tree-$label.json" | tail -1
  NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 "$SB/envs/driver/bin/python" -I scripts/sample_whoami.py "http://localhost:$port" 60 --json "out/whoami-$label.json" | tail -1
  ./scripts/serve.sh stop "$label" "$sig"
fi
echo "workers spawned: $(grep -c 'Spawning worker' "logs/$label.log"); unexpected-exit: $(grep -c 'Unexpected exit' "logs/$label.log"); tracebacks: $(grep -c 'Traceback' "logs/$label.log"); spawning-instead: $(grep -c -i 'spawning' "logs/$label.log")"
grep -n "Error\|error:\|Exception\|invalid\|Invalid" "logs/$label.log" | grep -v "errorBound\|error-boundary\|_error\|Debug: installed" | head -5 | cut -c1-220
