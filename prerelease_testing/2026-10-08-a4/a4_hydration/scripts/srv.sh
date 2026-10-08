#!/bin/bash
# Usage: srv.sh start <name> <venv:alpha2|alpha|stable|...> <dev|prod> <app_src_dir> <FP> <BP> [ENV=VAL...]
#        srv.sh stop <name>
#        srv.sh sync <name> <app_src_dir>   (re-copy sources into run/<name>, keeps .web)
# Copies the app's rxconfig.py + package .py files + assets into $W/run/<name> (keeps .web between starts),
# runs `reflex run` from there (neutral dir) in its own process group. Logs: $W/logs/<name>-<n>.log
set -u
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/a4_hydration
cmd=$1; name=$2
RUN=$W/run/$name
copy_src() {
  local SRC=$1; local app=$(basename $SRC)
  mkdir -p $RUN/$app $RUN/assets
  cp $SRC/rxconfig.py $RUN/ && cp $SRC/$app/*.py $RUN/$app/ && { [ -d $SRC/assets ] && cp -r $SRC/assets/. $RUN/assets/ || true; }
}
case $cmd in
  sync) copy_src $3; echo "synced $RUN";;
  start)
    venv=$3; mode=$4; SRC=$5; FP=$6; BP=$7; shift 7
    for p in $FP $BP; do
      if ! { [ $p -ge 3140 ] && [ $p -le 3159 ]; } && ! { [ $p -ge 8140 ] && [ $p -le 8159 ]; }; then echo "PORT $p OUT OF RANGE"; exit 3; fi
    done
    copy_src $SRC
    n=$(ls $W/logs/$name-*.log 2>/dev/null | wc -l); n=$((n+1)); LOG=$W/logs/$name-$n.log
    if [ "$mode" = prod ]; then API=http://localhost:$FP; else API=http://localhost:$BP; fi
    cd $RUN
    setsid env REFLEX_TELEMETRY_ENABLED=false REFLEX_API_URL=$API RVH_VENV=$venv VERIFY_VENV=$venv "$@" \
      $SB/envs/$venv/bin/reflex run --env $mode --frontend-port $FP --backend-port $BP --loglevel debug > $LOG 2>&1 < /dev/null &
    echo $! > $W/run/$name.pid
    echo "started $name pid=$(cat $W/run/$name.pid) venv=$venv mode=$mode env=[$*] log=$LOG";;
  stop)
    pid=$(cat $W/run/$name.pid 2>/dev/null)
    if [ -n "$pid" ]; then
      kill -TERM -- -$pid 2>/dev/null
      for i in $(seq 1 40); do ps -o pid= -g $pid >/dev/null 2>&1 || break; sleep 0.5; done
      if ps -o pid= -g $pid >/dev/null 2>&1; then kill -KILL -- -$pid 2>/dev/null; echo "SIGKILLed group $pid"; fi
      rm -f $W/run/$name.pid
      echo "stopped $name (pgid $pid)"
    fi
    lsof -iTCP -sTCP:LISTEN -P -n 2>/dev/null | grep -E ':(31[45][0-9]|81[45][0-9]) ' || echo "no listeners in reserved range";;
esac
