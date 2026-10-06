#!/bin/bash
# Usage: srv.sh start <name> <venv:alpha|stable> <dev|prod> <FP> <BP> [extra env assignments...]
#        srv.sh stop <name>
#        srv.sh sync <name>   (copy canonical app source into run/<name>)
set -u
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
H=$SB/apps/hydration
cmd=$1; name=$2
RUN=$H/run/$name
case $cmd in
  sync)
    mkdir -p $RUN
    mkdir -p $RUN/hydapp $RUN/assets && cp $H/hydapp/rxconfig.py $RUN/ && cp $H/hydapp/hydapp/*.py $RUN/hydapp/ && cp -r $H/hydapp/assets/. $RUN/assets/
    echo "synced $RUN";;
  start)
    venv=$3; mode=$4; FP=$5; BP=$6; shift 6
    mkdir -p $RUN
    mkdir -p $RUN/hydapp $RUN/assets && cp $H/hydapp/rxconfig.py $RUN/ && cp $H/hydapp/hydapp/*.py $RUN/hydapp/ && cp -r $H/hydapp/assets/. $RUN/assets/
    n=$(ls $H/logs/$name-*.log 2>/dev/null | wc -l); n=$((n+1))
    LOG=$H/logs/$name-$n.log
    if [ "$mode" = prod ]; then API=http://localhost:$FP; else API=http://localhost:$BP; fi
    cd $RUN
    setsid env REFLEX_TELEMETRY_ENABLED=false REFLEX_API_URL=$API "$@" \
      $SB/envs/$venv/bin/reflex run --env $mode --frontend-port $FP --backend-port $BP --loglevel debug > $LOG 2>&1 < /dev/null &
    echo $! > $H/run/$name.pid
    echo "started $name pid=$(cat $H/run/$name.pid) log=$LOG";;
  stop)
    pid=$(cat $H/run/$name.pid 2>/dev/null)
    if [ -n "$pid" ]; then
      kill -TERM -- -$pid 2>/dev/null
      for i in $(seq 1 30); do
        if ! ps -o pid= -g $pid >/dev/null 2>&1; then break; fi
        sleep 0.5
      done
      if ps -o pid= -g $pid >/dev/null 2>&1; then kill -KILL -- -$pid 2>/dev/null; echo "SIGKILLed group $pid"; fi
      echo "stopped $name (pgid $pid)"
    fi
    lsof -iTCP -sTCP:LISTEN -P -n 2>/dev/null | grep -E ':(32[2-3][0-9]|82[2-3][0-9]) ' || echo "no listeners in reserved range";;
esac
