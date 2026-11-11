#!/bin/bash
# Usage: run_app.sh <venv-name> <app_dir> <tag> <frontend_port> <backend_port> [extra reflex run args...]
# Starts `reflex run` in its own process group from a COPY-free app dir (never a checkout); pid in $W/pids/<tag>.pid,
# log in $W/logs/<tag>.log. Env passthrough: FORMS_NEW, FORMS_API_URL, REFLEX_REDIS_URL, EXPECT_VENV (set from venv name).
set -u
: "${SB:?}"; W=${W:-$SB/apps/verify_es}; mkdir -p "$W/pids" "$W/logs"
V=$1; APP=$2; TAG=$3; FP=$4; BP=$5; shift 5
for p in $FP $BP; do
  if [ "$p" -lt 3760 ] || { [ "$p" -gt 3779 ] && [ "$p" -lt 8760 ]; } || [ "$p" -gt 8779 ]; then echo "port $p outside 3760-3779/8760-8779"; exit 1; fi
done
export EXPECT_VENV=$V REFLEX_TELEMETRY_ENABLED=false
cd "$APP" || exit 1
rm -f form_log.jsonl
setsid "$SB/envs/$V/bin/reflex" run --frontend-port "$FP" --backend-port "$BP" "$@" > "$W/logs/$TAG.log" 2>&1 < /dev/null &
echo $! > "$W/pids/$TAG.pid"
echo "started pgid=$! venv=$V app=$APP fp=$FP bp=$BP log=$W/logs/$TAG.log"
