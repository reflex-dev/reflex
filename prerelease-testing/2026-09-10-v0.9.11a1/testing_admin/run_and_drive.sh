#!/bin/bash
# run_and_drive.sh <venv> <label> <appdir> <driver.py> [extra driver args]
# Starts `reflex run` on the cluster's reserved ports (5580/9980), waits for BOTH
# the frontend and the backend, runs the driver, then kills everything it started.
set -u
VENV=$1; LABEL=$2; APP=$3; DRV=$4; shift 4
D="$(cd "$(dirname "$0")" && pwd)"
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
FP=5580; BP=9980
LOG="$D/logs/run_${LABEL}.log"
bash "$D/kill_servers.sh" > /dev/null 2>&1
cd "$APP" || exit 1
REFLEX_TELEMETRY_ENABLED=false "$VENV/bin/reflex" run --frontend-port $FP --backend-port $BP --loglevel debug > "$LOG" 2>&1 &
PID=$!
fcode=000; bcode=000
for i in $(seq 1 140); do
  fcode=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' "http://localhost:$FP/" 2>/dev/null)
  bcode=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' "http://localhost:$BP/ping" 2>/dev/null)
  [ "$fcode" = "200" ] && [ "$bcode" = "200" ] && break
  sleep 3
done
echo "frontend_http=$fcode backend_ping=$bcode"
if [ "$fcode" = "200" ] && [ "$bcode" = "200" ]; then
  (cd /tmp && "$SB/envs/driver/bin/python" "$DRV" "http://localhost:$FP/" "$@") > "$D/logs/drive_${LABEL}.json" 2>&1
  echo "driver_exit=$?"
else
  echo "SERVER DID NOT COME UP - see $LOG"
fi
kill "$PID" 2>/dev/null
sleep 3
bash "$D/kill_servers.sh" > /dev/null 2>&1
