#!/bin/bash
# usage: srv.sh start <venv> <appdir> <dev|prod> <fp> <bp> <tag> [redis_url] | srv.sh stop <tag>
SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad
L=$SB/apps/verify_evt/logs; mkdir -p $L
if [ "$1" = start ]; then
  venv=$2 app=$3 env=$4 fp=$5 bp=$6 tag=$7 redis=$8
  for p in $fp $bp; do curl -s --noproxy '*' -o /dev/null -m 2 localhost:$p && { echo "port $p busy"; exit 1; }; done
  cd $app
  extra=(); [ "$env" = prod ] && export REFLEX_API_URL=http://localhost:$bp
  [ -n "$redis" ] && export REFLEX_REDIS_URL=$redis
  REFLEX_TELEMETRY_ENABLED=false setsid $SB/envs/$venv/bin/reflex run --env $env --frontend-port $fp --backend-port $bp > $L/$tag.log 2>&1 &
  echo $! > $L/$tag.pid
  for i in $(seq 1 72); do c=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' -m 3 localhost:$fp/); [ "$c" = 200 ] && { echo "up after $((i*5))s"; exit 0; }; sleep 5; done
  echo "not up"; tail -20 $L/$tag.log; exit 1
else
  tag=$2; P=$(cat $L/$tag.pid); kill -INT -- -$P 2>/dev/null; for i in 1 2 3 4 5 6 7 8; do sleep 1; ps -o pid= -g $P >/dev/null 2>&1 || { echo "stopped in ${i}s"; exit 0; }; done; kill -9 -- -$P 2>/dev/null; echo "killed -9"
fi
