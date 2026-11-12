#!/bin/bash
# srv.sh start <venv> <appdir> <dev|prod> <tag> [extra env...] | stop <tag>
W=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/final
FP=3500; BP=8500
cmd=$1; shift
case $cmd in
start)
  venv=$1 app=$2 mode=$3 tag=$4; shift 4
  for p in $FP $BP; do curl -s --noproxy '*' -m 2 localhost:$p >/dev/null && { echo "port $p busy"; exit 1; }; done
  cd "$app" || exit 1
  if [ "$mode" = prod ]; then
    env REFLEX_TELEMETRY_ENABLED=false REFLEX_API_URL=http://localhost:$FP "$@" setsid "$venv/bin/reflex" run --env prod --frontend-port $FP --backend-port $FP --loglevel debug > $W/logs/$tag.server.log 2>&1 < /dev/null &
    url=http://localhost:$FP/
  else
    env REFLEX_TELEMETRY_ENABLED=false "$@" setsid "$venv/bin/reflex" run --frontend-port $FP --backend-port $BP --loglevel debug > $W/logs/$tag.server.log 2>&1 < /dev/null &
    url=http://localhost:$FP/
  fi
  echo $! > $W/logs/$tag.pid
  for i in $(seq 1 180); do
    code=$(curl -s --noproxy '*' -m 3 -o /dev/null -w '%{http_code}' $url)
    [ "$code" = 200 ] && { echo "up after ${i}x2s ($url)"; exit 0; }
    kill -0 $(cat $W/logs/$tag.pid) 2>/dev/null || { echo "server died"; tail -30 $W/logs/$tag.server.log; exit 1; }
    sleep 2
  done
  echo "timeout"; exit 1;;
stop)
  tag=$1; pid=$(cat $W/logs/$tag.pid)
  kill -INT -- -$pid 2>/dev/null; for i in $(seq 1 15); do kill -0 -- -$pid 2>/dev/null || break; sleep 1; done
  kill -9 -- -$pid 2>/dev/null
  sleep 1
  for p in $FP $BP; do curl -s --noproxy '*' -m 2 localhost:$p >/dev/null && echo "port $p STILL busy"; done
  echo stopped $tag;;
esac
