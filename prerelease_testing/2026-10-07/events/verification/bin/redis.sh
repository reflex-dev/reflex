#!/usr/bin/env bash
# usage: redis.sh start|stop|flush
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/verify_events_0
case $1 in
  start)
    if redis-cli -p 8659 ping >/dev/null 2>&1; then echo "redis already up"; exit 0; fi
    setsid nohup redis-server --port 8659 --save '' --appendonly no > $W/logs/redis.log 2>&1 < /dev/null &
    echo $! > $W/pids/redis.pid
    for i in $(seq 1 20); do redis-cli -p 8659 ping >/dev/null 2>&1 && { echo "redis up (pid $(cat $W/pids/redis.pid))"; exit 0; }; sleep 0.5; done
    echo "redis failed to start"; exit 1 ;;
  flush) redis-cli -p 8659 flushall ;;
  stop)
    redis-cli -p 8659 shutdown nosave 2>/dev/null
    [ -f $W/pids/redis.pid ] && kill $(cat $W/pids/redis.pid) 2>/dev/null; rm -f $W/pids/redis.pid; echo "redis stopped" ;;
esac
