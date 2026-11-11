#!/bin/bash
# Usage: run_app.sh <venv-name> <app_dir> <tag> <frontend_port> <backend_port> [extra reflex run args...]
# Starts `reflex run` in its own process group from a COPY-free app dir (never a checkout); pid in $W/pids/<tag>.pid,
# log in $W/logs/<tag>.log. Env passthrough: FORMS_NEW, FORMS_API_URL, REFLEX_REDIS_URL, EXPECT_VENV (set from venv name).
set -u
: "${SB:?}"; W=${W:-$SB/apps/events_state}; mkdir -p "$W/pids" "$W/logs"
V=$1; APP=$2; TAG=$3; FP=$4; BP=$5; shift 5
for p in $FP $BP; do
  if [ "$p" -lt 3300 ] || { [ "$p" -gt 3319 ] && [ "$p" -lt 8300 ]; } || [ "$p" -gt 8319 ]; then echo "port $p outside 3300-3319/8300-8319"; exit 1; fi
done
export EXPECT_VENV=$V REFLEX_TELEMETRY_ENABLED=false
cd "$APP" || exit 1
rm -f form_log.jsonl
setsid "$SB/envs/$V/bin/reflex" run --frontend-port "$FP" --backend-port "$BP" "$@" > "$W/logs/$TAG.log" 2>&1 < /dev/null &
echo $! > "$W/pids/$TAG.pid"
echo "started pgid=$! venv=$V app=$APP fp=$FP bp=$BP log=$W/logs/$TAG.log"
