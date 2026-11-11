#!/usr/bin/env bash
# Usage: srv.sh start <name> <venv> <dev|prod> <appdir> <fp> <bp> [VAR=VAL ...]
#        srv.sh stop <name>
# Logs: $SB/apps/compile_memo/logs/<name>.log ; pgid file: logs/<name>.pgid
set -u
SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad
L=$SB/apps/compile_memo/logs
cmd=$1; name=$2
if [ "$cmd" = stop ]; then
  pg=$(cat $L/$name.pgid 2>/dev/null) || exit 0
  kill -INT -- -$pg 2>/dev/null; for i in $(seq 1 20); do kill -0 -- -$pg 2>/dev/null || break; sleep 0.5; done
  kill -9 -- -$pg 2>/dev/null; rm -f $L/$name.pgid; echo "stopped $name"; exit 0
fi
venv=$3; mode=$4; app=$5; fp=$6; bp=$7; shift 7
for p in $fp $bp; do
  if curl -s --noproxy '*' -o /dev/null localhost:$p; then echo "PORT $p BUSY"; exit 1; fi
done
cd $app
extra=()
if [ "$mode" = prod ]; then extra=(--env prod); export REFLEX_API_URL=http://localhost:$bp; fi
export REFLEX_TELEMETRY_ENABLED=false
for kv in "$@"; do export "$kv"; done
setsid $SB/envs/$venv/bin/reflex run --frontend-port $fp --backend-port $bp "${extra[@]}" --loglevel info > $L/$name.log 2>&1 &
pid=$!
echo $pid > $L/$name.pgid
url=http://localhost:$fp/
t0=$(date +%s)
for i in $(seq 1 360); do
  code=$(curl -s --noproxy '*' -o /dev/null -w "%{http_code}" $url)
  [ "$code" = 200 ] && break
  kill -0 $pid 2>/dev/null || { echo "server died"; tail -20 $L/$name.log; exit 1; }
  sleep 1
done
echo "up $name in $(( $(date +%s) - t0 ))s code=$code"
