#!/usr/bin/env bash
# usage: start.sh <venv-name> <app-dir> <log-file> <mode prod|dev> <frontend-port> <backend-port> [extra env assignments...]
# Starts `reflex run` in its own process group (setsid), records the pgid in pids/current.pgid,
# and polls the frontend URL for up to 6 minutes. Server env: CI=true REFLEX_TELEMETRY_ENABLED=false
# (NO proxy bypass variables are exported to the server).
set -u
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/verify_ent_grid_0
VENV=$1; APP=$2; LOG=$3; MODE=$4; FP=$5; BP=$6; shift 6
for p in $FP $BP; do
  if [ "$p" -lt 3680 ] || { [ "$p" -gt 3699 ] && [ "$p" -lt 8680 ]; } || [ "$p" -gt 8699 ]; then echo "port $p outside reserved range"; exit 2; fi
  if lsof -iTCP:$p -sTCP:LISTEN -nP >/dev/null 2>&1; then echo "port $p busy"; lsof -iTCP:$p -sTCP:LISTEN -nP; exit 2; fi
done
ARGS=(run --frontend-port $FP --backend-port $BP --loglevel debug)
[ "$MODE" = prod ] && ARGS+=(--env prod)
cd "$APP" || exit 2
echo "[start.sh] $(date -u +%FT%TZ) venv=$VENV app=$APP mode=$MODE fp=$FP bp=$BP extra=$*" > "$LOG"
env CI=true REFLEX_TELEMETRY_ENABLED=false VERIFY_BACKEND_PORT=$BP "$@" \
  setsid $SB/envs/$VENV/bin/reflex "${ARGS[@]}" >> "$LOG" 2>&1 < /dev/null &
PID=$!
sleep 1
PGID=$(ps -o pgid= -p $PID | tr -d ' ')
echo "$PGID" > $W/pids/current.pgid
echo "started pid=$PID pgid=$PGID"
for i in $(seq 1 180); do
  code=$(NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:$FP/ 2>/dev/null)
  bcode=$(NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:$BP/ping 2>/dev/null)
  if [ "$code" = 200 ] && [ "$bcode" = 200 ]; then echo "ready after $((i*2))s (frontend 200, /ping 200)"; exit 0; fi
  if ! kill -0 $PID 2>/dev/null; then echo "server exited"; tail -30 "$LOG"; exit 1; fi
  sleep 2
done
echo "not ready after 6 min"; tail -30 "$LOG"; exit 1
