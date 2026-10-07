#!/bin/bash
# Usage: vsrv.sh start <name> <venv:alpha|stable> <dev|prod> <app_src_dir> <FP> <BP> [ENV=VAL...]
#        vsrv.sh stop <name>
# Copies the app's rxconfig.py + package .py files + assets into $V/run/<name> (keeps .web between starts).
set -u
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
V=$SB/apps/verify_hydration_0
cmd=$1; name=$2
RUN=$V/run/$name
case $cmd in
  start)
    venv=$3; mode=$4; SRC=$5; FP=$6; BP=$7; shift 7
    app=$(basename $SRC)
    mkdir -p $RUN/$app $RUN/assets
    cp $SRC/rxconfig.py $RUN/ && cp $SRC/$app/*.py $RUN/$app/ && { [ -d $SRC/assets ] && cp -r $SRC/assets/. $RUN/assets/ || true; }
    n=$(ls $V/logs/$name-*.log 2>/dev/null | wc -l); n=$((n+1)); LOG=$V/logs/$name-$n.log
    if [ "$mode" = prod ]; then API=http://localhost:$FP; else API=http://localhost:$BP; fi
    cd $RUN
    setsid env REFLEX_TELEMETRY_ENABLED=false REFLEX_API_URL=$API "$@" \
      $SB/envs/$venv/bin/reflex run --env $mode --frontend-port $FP --backend-port $BP --loglevel debug > $LOG 2>&1 < /dev/null &
    echo $! > $V/run/$name.pid
    echo "started $name pid=$(cat $V/run/$name.pid) log=$LOG";;
  stop)
    pid=$(cat $V/run/$name.pid 2>/dev/null)
    if [ -n "$pid" ]; then
      kill -TERM -- -$pid 2>/dev/null
      for i in $(seq 1 30); do ps -o pid= -g $pid >/dev/null 2>&1 || break; sleep 0.5; done
      if ps -o pid= -g $pid >/dev/null 2>&1; then kill -KILL -- -$pid 2>/dev/null; echo "SIGKILLed group $pid"; fi
      echo "stopped $name (pgid $pid)"
    fi
    ss -ltnp 2>/dev/null | grep -E ':(372[0-7]|872[0-7])\b' || echo "no listeners in reserved range";;
esac
