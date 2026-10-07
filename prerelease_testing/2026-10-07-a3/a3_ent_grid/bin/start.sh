#!/usr/bin/env bash
# usage: start.sh <venv-name> <app-dir> <log-file> <mode prod|dev> <frontend-port> <backend-port> [extra env assignments...]
# Starts `reflex run` in its own process group (setsid), records the pgid in pids/current.pgid,
# and polls the frontend URL (+ backend /ping) for up to 6 minutes. Server env: CI=true REFLEX_TELEMETRY_ENABLED=false
# (NO proxy bypass variables are exported to the server). Ports restricted to 3300-3319 / 8300-8319 (a3_ent_grid).
set -u
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/a3_ent_grid
VENV=$1; APP=$2; LOG=$3; MODE=$4; FP=$5; BP=$6; shift 6
for p in $FP $BP; do
  if [ "$p" -lt 3300 ] || { [ "$p" -gt 3319 ] && [ "$p" -lt 8300 ]; } || [ "$p" -gt 8319 ]; then echo "port $p outside reserved range"; exit 2; fi
  if lsof -iTCP:$p -sTCP:LISTEN -nP >/dev/null 2>&1; then echo "port $p busy"; lsof -iTCP:$p -sTCP:LISTEN -nP; exit 2; fi
done
if [ -s $W/pids/current.pgid ] && pgrep -g "$(cat $W/pids/current.pgid)" >/dev/null; then echo "a server (pgid $(cat $W/pids/current.pgid)) is still running; run bin/stop.sh first"; exit 2; fi
ARGS=(run --frontend-port $FP --backend-port $BP --loglevel debug)
[ "$MODE" = prod ] && ARGS+=(--env prod)
cd "$APP" || exit 2
VERS=$(cd $SB && $SB/envs/$VENV/bin/python -I $W/bin/vers.py)
echo "[start.sh] $(date -u +%FT%TZ) venv=$VENV ($VERS) app=$APP mode=$MODE fp=$FP bp=$BP extra=$*" > "$LOG"
echo "[start.sh] venv=$VENV $VERS"
env CI=true REFLEX_TELEMETRY_ENABLED=false VERIFY_BACKEND_PORT=$BP VERIFY_VENV=$VENV "$@" \
  setsid $SB/envs/$VENV/bin/reflex "${ARGS[@]}" >> "$LOG" 2>&1 < /dev/null &
PID=$!
sleep 1
PGID=$(ps -o pgid= -p $PID | tr -d ' ')
echo "$PGID" > $W/pids/current.pgid
echo "started pid=$PID pgid=$PGID"
for i in $(seq 1 180); do
  code=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' --max-time 5 http://localhost:$FP/ 2>/dev/null)
  bcode=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' --max-time 5 http://localhost:$BP/ping 2>/dev/null)
  if [ "$code" = 200 ] && [ "$bcode" = 200 ]; then echo "ready after $((i*2))s (frontend 200, /ping 200)"; exit 0; fi
  if ! kill -0 $PID 2>/dev/null; then echo "server exited"; tail -30 "$LOG"; exit 1; fi
  sleep 2
done
echo "not ready after 6 min"; tail -30 "$LOG"; exit 1
