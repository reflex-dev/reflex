#!/bin/bash
# verify_hydration server helper.
# Usage: vsrv.sh start <name> <venv:a3|alpha2|stable> <dev|prod> <app_src_dir> <FP> <BP> [ENV=VAL...]
#        vsrv.sh stop <name>
# Copies rxconfig.py + the app package (+assets) into $V/run/<name> (keeps .web between starts), runs `reflex run`
# from there (a neutral dir, never a checkout) in its own process group. Logs: $V/logs/<name>-<n>.log
# The app asserts reflex.__file__ is under /scratchpad/envs/$VH_VENV/ (and RVH_VENV for the explorer's apps).
set -u
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
V=$SB/apps/verify_hydration
cmd=$1; name=$2
RUN=$V/run/$name
case $cmd in
  start)
    venv=$3; mode=$4; SRC=$5; FP=$6; BP=$7; shift 7
    for p in $FP $BP; do
      if ! { [ $p -ge 3660 ] && [ $p -le 3679 ]; } && ! { [ $p -ge 8660 ] && [ $p -le 8679 ]; }; then echo "PORT $p OUT OF RANGE"; exit 3; fi
    done
    app=$(basename $SRC)
    mkdir -p $RUN/$app $RUN/assets
    cp $SRC/rxconfig.py $RUN/ && cp $SRC/$app/*.py $RUN/$app/ && { [ -d $SRC/assets ] && cp -r $SRC/assets/. $RUN/assets/ || true; }
    n=$(ls $V/logs/$name-*.log 2>/dev/null | wc -l); n=$((n+1)); LOG=$V/logs/$name-$n.log
    if [ "$mode" = prod ]; then API=http://localhost:$FP; else API=http://localhost:$BP; fi
    cd $RUN
    setsid env REFLEX_TELEMETRY_ENABLED=false REFLEX_API_URL=$API VH_VENV=$venv RVH_VENV=$venv "$@" \
      $SB/envs/$venv/bin/reflex run --env $mode --frontend-port $FP --backend-port $BP --loglevel debug > $LOG 2>&1 < /dev/null &
    echo $! > $V/run/$name.pid
    echo "started $name pid=$(cat $V/run/$name.pid) venv=$venv mode=$mode env=[$*] log=$LOG";;
  stop)
    pid=$(cat $V/run/$name.pid 2>/dev/null)
    if [ -n "$pid" ]; then
      kill -TERM -- -$pid 2>/dev/null
      for i in $(seq 1 40); do ps -o pid= -g $pid >/dev/null 2>&1 || break; sleep 0.5; done
      if ps -o pid= -g $pid >/dev/null 2>&1; then kill -KILL -- -$pid 2>/dev/null; echo "SIGKILLed group $pid"; fi
      rm -f $V/run/$name.pid
      echo "stopped $name (pgid $pid)"
    fi
    lsof -iTCP -sTCP:LISTEN -P -n 2>/dev/null | grep -E ':(36[67][0-9]|86[67][0-9]) ' || echo "no listeners in reserved range";;
esac
