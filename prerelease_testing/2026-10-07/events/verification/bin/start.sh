#!/usr/bin/env bash
# usage: start.sh <venv: alpha2|alpha|stable> <dev|prod> <disk|memory|redis> [KEY=VAL ...]
# Starts ONE reflex server on the reserved ports (dev FE 3640/BE 8640; prod single port 8641).
# The run dir run/<venv>_<mode> is reused between state-manager variants (keeps .web).
set -u
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/verify_events_0
VENV=$1; MODE=$2; SM=$3; shift 3
RUN=$W/run/${VENV}_${MODE}
LABEL=${VENV}_${MODE}_${SM}
EXTRA_LABEL="${EVV_LABEL_SUFFIX:-}"
LABEL=${LABEL}${EXTRA_LABEL}
FP=3640; BP=8640; PP=8641
mkdir -p "$RUN" $W/logs $W/pids
# copy app source, keep generated dirs (.web, .states) so re-starts are fast
for f in rxconfig.py; do cp "$W/app/$f" "$RUN/$f"; done
mkdir -p "$RUN/evv"; cp "$W/app/evv/"*.py "$RUN/evv/"
cd "$RUN" || exit 1
unset REFLEX_REDIS_URL REFLEX_STATE_MANAGER_MODE GRANIAN_WORKERS
export REFLEX_TELEMETRY_ENABLED=false EVV_VENV=$VENV
case $SM in
  redis)  export REFLEX_REDIS_URL=redis://localhost:8659 ;;
  memory) export REFLEX_STATE_MANAGER_MODE=memory ;;
  disk)   ;;
  *) echo "bad sm $SM"; exit 2 ;;
esac
for kv in "$@"; do export "$kv"; done
if [ "$MODE" = prod ]; then
  export REFLEX_API_URL=http://localhost:$PP
  CMD="$SB/envs/$VENV/bin/reflex run --env prod --frontend-port $PP --backend-port $PP --loglevel debug"
else
  CMD="$SB/envs/$VENV/bin/reflex run --env dev --frontend-port $FP --backend-port $BP --loglevel debug"
fi
echo "[start.sh] $(date -u +%H:%M:%S) label=$LABEL cwd=$RUN cmd=$CMD redis=${REFLEX_REDIS_URL:-} sm=${REFLEX_STATE_MANAGER_MODE:-} workers=${GRANIAN_WORKERS:-default}"
setsid nohup $CMD > "$W/logs/$LABEL.log" 2>&1 < /dev/null &
echo $! > "$W/pids/$LABEL.pid"
echo "[start.sh] pid=$(cat $W/pids/$LABEL.pid) log=$W/logs/$LABEL.log"
