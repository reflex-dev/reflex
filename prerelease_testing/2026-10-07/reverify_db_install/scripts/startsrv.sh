#!/usr/bin/env bash
# usage: startsrv.sh <venv> <appdir> <fp> <bp> <logfile> [prod] [extra env assignments...]
# starts `reflex run` detached (setsid), waits (<=6min) for the frontend to answer 200.
venv=$1; app=$2; fp=$3; bp=$4; log=$5; mode=${6:-dev}; shift 6 2>/dev/null || shift $#
cd "$app" || exit 2
if [ "$mode" = prod ]; then
  env REFLEX_TELEMETRY_ENABLED=false REFLEX_API_URL=http://localhost:$fp "$@" setsid nohup "$venv/bin/reflex" run --env prod --frontend-port $fp --backend-port $fp --loglevel debug > "$log" 2>&1 &
  port=$fp
else
  env REFLEX_TELEMETRY_ENABLED=false "$@" setsid nohup "$venv/bin/reflex" run --frontend-port $fp --backend-port $bp --loglevel debug > "$log" 2>&1 &
  port=$fp
fi
for i in $(seq 1 72); do
  code=$(curl -s --noproxy '*' -o /dev/null -w "%{http_code}" http://localhost:$port/)
  [ "$code" = 200 ] && { echo "frontend up after ~$((i*5))s"; exit 0; }
  sleep 5
done
echo "frontend NOT up (last code $code)"; tail -20 "$log"; exit 1
