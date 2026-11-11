#!/usr/bin/env bash
# Start/stop a reflex app server in its own process group.
# usage: srv.sh start <venv> <appdir> <dev|prod> <fe_port> <be_port> <tag> [redis]   (extra env via SRV_ENV="K=V K2=V2")
#        srv.sh stop <tag>
#        srv.sh redis-start | redis-stop
SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad
A=$SB/apps/events_await
LOGS=$A/logs
mkdir -p "$LOGS"
cmd=$1; shift
case "$cmd" in
  start)
    venv=$1 appdir=$2 mode=$3 fp=$4 bp=$5 tag=$6 redis=${7:-}
    for p in $fp $bp; do
      if curl -s --noproxy '*' -o /dev/null "localhost:$p"; then echo "port $p busy"; exit 1; fi
    done
    cd "$appdir" || exit 1
    envs=(REFLEX_TELEMETRY_ENABLED=false AWAIT_MW_LOG="$LOGS/$tag.mw.jsonl")
    [ -n "$redis" ] && envs+=(REFLEX_REDIS_URL=redis://localhost:8199)
    for kv in ${SRV_ENV:-}; do envs+=("$kv"); done
    : > "$LOGS/$tag.log"; : > "$LOGS/$tag.mw.jsonl"
    if [ "$mode" = prod ]; then
      envs+=(REFLEX_API_URL=http://localhost:$fp)
      env "${envs[@]}" setsid "$SB/envs/$venv/bin/reflex" run --env prod --frontend-port "$fp" --backend-port "$fp" ${SRV_ARGS:-} >> "$LOGS/$tag.log" 2>&1 &
    else
      env "${envs[@]}" setsid "$SB/envs/$venv/bin/reflex" run --frontend-port "$fp" --backend-port "$bp" ${SRV_ARGS:-} >> "$LOGS/$tag.log" 2>&1 &
    fi
    echo $! > "$LOGS/$tag.pid"
    for i in $(seq 1 180); do
      code=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' "localhost:$fp/" || true)
      if [ "$code" = 200 ]; then
        if [ "$mode" = prod ] || curl -s --noproxy '*' -o /dev/null "localhost:$bp/ping"; then echo "up after ${i}x2s (pid $(cat $LOGS/$tag.pid))"; exit 0; fi
      fi
      if ! kill -0 "$(cat $LOGS/$tag.pid)" 2>/dev/null; then echo "server died"; tail -30 "$LOGS/$tag.log"; exit 1; fi
      sleep 2
    done
    echo "timeout"; tail -30 "$LOGS/$tag.log"; exit 1
    ;;
  stop)
    tag=$1
    pid=$(cat "$LOGS/$tag.pid" 2>/dev/null) || exit 0
    t0=$(date +%s.%N)
    kill -INT -- "-$pid" 2>/dev/null
    for i in $(seq 1 60); do
      if ! pgrep -g "$pid" >/dev/null 2>&1; then break; fi
      sleep 0.5
    done
    t1=$(date +%s.%N)
    if pgrep -g "$pid" >/dev/null 2>&1; then
      echo "group $pid still alive after 30s SIGINT; killing -9:"; pgrep -g "$pid" -a | cut -c1-150
      kill -9 -- "-$pid" 2>/dev/null
    else
      echo "stopped $tag in $(echo "$t1 - $t0" | bc)s"
    fi
    rm -f "$LOGS/$tag.pid"
    ;;
  redis-start)
    if redis-cli -p 8199 ping >/dev/null 2>&1; then echo "redis already up"; exit 0; fi
    setsid redis-server --port 8199 --save '' --appendonly no > "$LOGS/redis.log" 2>&1 &
    echo $! > "$LOGS/redis.pid"; sleep 1; redis-cli -p 8199 ping
    ;;
  redis-stop)
    redis-cli -p 8199 shutdown nosave >/dev/null 2>&1; rm -f "$LOGS/redis.pid"; echo redis stopped
    ;;
esac
