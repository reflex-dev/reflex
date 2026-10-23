#!/usr/bin/env bash
# Start / stop reflex servers for the frontend_store item, tracking PIDs.
#   serve.sh start <venv> <appdir> <mode:dev|prod> <fport> <bport> <logname> [extra reflex args...]
#   serve.sh stop <logname>
#   serve.sh wait <url> [seconds]
# Env passed through: EXPECT_VENV, FS_TRUTH, FS_NEGSQ, FS_TW_IMPORTANT, REFLEX_REACT_COMPILER,
# REFLEX_REDIS_URL, REFLEX_AUTO_RELOAD_COOLDOWN, REFLEX_BACKEND_START_METHOD, GRANIAN_WORKERS.
set -u
SB=${SB:-/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa}
WORK=$SB/apps/frontend_store
LOGS=$WORK/logs
mkdir -p "$LOGS"
cmd=$1; shift
case "$cmd" in
  start)
    venv=$1; appdir=$2; mode=$3; fport=$4; bport=$5; logname=$6; shift 6
    cd "$appdir" || exit 1
    export REFLEX_TELEMETRY_ENABLED=false
    export EXPECT_VENV=${EXPECT_VENV:-$venv}
    if [ "$mode" = prod ]; then
      export REFLEX_API_URL=http://localhost:$bport
      nohup "$SB/envs/$venv/bin/reflex" run --env prod --frontend-port "$fport" --backend-port "$bport" --loglevel debug "$@" \
        > "$LOGS/$logname.log" 2>&1 &
    else
      nohup "$SB/envs/$venv/bin/reflex" run --frontend-port "$fport" --backend-port "$bport" --loglevel debug "$@" \
        > "$LOGS/$logname.log" 2>&1 &
    fi
    echo $! > "$LOGS/$logname.pid"
    echo "started $logname pid $(cat "$LOGS/$logname.pid") log $LOGS/$logname.log"
    ;;
  stop)
    logname=$1
    if [ -f "$LOGS/$logname.pid" ]; then
      pid=$(cat "$LOGS/$logname.pid")
      # kill the whole process group of the reflex process (granian supervisor, bun/vite children)
      pkill -TERM -P "$pid" 2>/dev/null; kill -TERM "$pid" 2>/dev/null
      for i in $(seq 1 30); do kill -0 "$pid" 2>/dev/null || break; sleep 0.5; done
      kill -0 "$pid" 2>/dev/null && { pkill -KILL -P "$pid" 2>/dev/null; kill -KILL "$pid" 2>/dev/null; }
      rm -f "$LOGS/$logname.pid"
      echo "stopped $logname ($pid)"
    fi
    ;;
  wait)
    url=$1; secs=${2:-360}
    for i in $(seq 1 "$secs"); do
      code=$(curl --noproxy '*' -s -o /dev/null -w '%{http_code}' "$url" 2>/dev/null)
      if [ "$code" = 200 ]; then echo "up after ${i}s ($url)"; exit 0; fi
      sleep 1
    done
    echo "NOT UP after ${secs}s ($url) last code=$code"; exit 1
    ;;
esac
