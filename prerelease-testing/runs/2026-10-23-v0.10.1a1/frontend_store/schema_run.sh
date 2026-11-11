#!/usr/bin/env bash
# Schema-hash scenarios (#7553 / #7435) with schema_app.
#   schema_run.sh export <label> [ENV=..]   # frontend-only export -> $W/schema_app/static_<label> (api url :8227)
#   schema_run.sh static <label>            # serve static_<label> on :3227 (pid in logs/static.pid)
#   schema_run.sh backend <log> [ENV=..]    # prod backend-only on :8227 (pid in logs/<log>.pid)
#   schema_run.sh stop <log>
set -u
SB=${SB:-/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa}
W=$SB/apps/frontend_store
LOGS=$W/logs
VENV=${VENV:-new}
cmd=$1; shift
case "$cmd" in
  export)
    label=$1; shift
    cd $W/schema_app || exit 1
    env "$@" REFLEX_TELEMETRY_ENABLED=false EXPECT_VENV=$VENV REFLEX_API_URL=http://localhost:8227 \
      $SB/envs/$VENV/bin/reflex export --frontend-only --no-zip --loglevel debug > $LOGS/schema_export_$label.log 2>&1
    rc=$?
    rm -rf static_$label && cp -r .web/build/client static_$label
    echo "export $label rc=$rc -> $(ls static_$label | wc -l) entries; schema=$(grep -oE 'stateSchema = "[0-9a-f]+"' .web/utils/context.jsx)"
    ;;
  static)
    label=$1
    cd $W/schema_app || exit 1
    nohup $SB/envs/driver/bin/python $W/static_serve.py $W/schema_app/static_$label 3227 > $LOGS/static.log 2>&1 &
    echo $! > $LOGS/static.pid; sleep 1
    echo "static $label pid $(cat $LOGS/static.pid): $(curl --noproxy '*' -s -o /dev/null -w '%{http_code}' http://localhost:3227/)"
    ;;
  backend)
    log=$1; shift
    cd $W/schema_app || exit 1
    env "$@" REFLEX_TELEMETRY_ENABLED=false EXPECT_VENV=$VENV \
      nohup $SB/envs/$VENV/bin/reflex run --env prod --backend-only --backend-port 8227 --loglevel debug > $LOGS/$log.log 2>&1 &
    echo $! > $LOGS/$log.pid
    for i in $(seq 1 90); do curl --noproxy '*' -s -m 2 http://localhost:8227/ping | grep -q pong && break; sleep 1; done
    echo "backend $log pid $(cat $LOGS/$log.pid) up after ${i}s; schema=$(grep -oE 'backend state schema [0-9a-f]+' $LOGS/$log.log | head -1)"
    ;;
  stop)
    log=$1
    if [ -f $LOGS/$log.pid ]; then
      pid=$(cat $LOGS/$log.pid); pkill -TERM -P $pid 2>/dev/null; kill -TERM $pid 2>/dev/null
      for i in $(seq 1 30); do kill -0 $pid 2>/dev/null || break; sleep 0.5; done
      kill -0 $pid 2>/dev/null && { pkill -KILL -P $pid 2>/dev/null; kill -KILL $pid 2>/dev/null; }
      rm -f $LOGS/$log.pid; echo "stopped $log ($pid)"
    fi
    ;;
esac
