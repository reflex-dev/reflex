#!/bin/bash
# Usage: mini.sh start <alpha|stable> <PORT> [ENV=VAL...] | mini.sh stop <alpha|stable>
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
H=$SB/apps/hydration
cmd=$1; venv=$2
RUN=$H/run/mini-$venv
case $cmd in
  start)
    port=$3; shift 3
    mkdir -p $RUN/mini_writeback $RUN/assets && cp $H/mini_writeback/rxconfig.py $RUN/ && cp $H/mini_writeback/mini_writeback/*.py $RUN/mini_writeback/ && cp -r $H/mini_writeback/assets/. $RUN/assets/
    n=$(ls $H/logs/mini-$venv-*.log 2>/dev/null | wc -l); n=$((n+1)); LOG=$H/logs/mini-$venv-$n.log
    cd $RUN
    setsid env REFLEX_TELEMETRY_ENABLED=false REFLEX_API_URL=http://localhost:$port "$@" $SB/envs/$venv/bin/reflex run --env prod --frontend-port $port --backend-port $port --loglevel debug > $LOG 2>&1 < /dev/null &
    echo $! > $H/run/mini-$venv.pid; echo "started mini-$venv pid=$(cat $H/run/mini-$venv.pid) log=$LOG";;
  stop)
    pid=$(cat $H/run/mini-$venv.pid); kill -TERM -- -$pid 2>/dev/null || echo "WARN: no process group $pid"
    for i in $(seq 1 30); do ps -o pid= -g $pid >/dev/null 2>&1 || break; sleep 0.5; done
    ps -o pid= -g $pid >/dev/null 2>&1 && kill -KILL -- -$pid; echo "stopped mini-$venv";;
esac
