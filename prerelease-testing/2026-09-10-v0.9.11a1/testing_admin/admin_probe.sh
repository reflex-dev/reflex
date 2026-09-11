#!/bin/bash
# Probe the /admin surface of the admindash app under one env.
#   admin_probe.sh <venv-dir> <label> <appdir> <backend-port>
set -u
VENV=$1; LABEL=$2; APP=$3; BP=$4
D="$(cd "$(dirname "$0")" && pwd)"
LOG="$D/logs/admin_${LABEL}.log"
OUT="$D/logs/admin_${LABEL}.status"
cd "$APP" || exit 1
REFLEX_TELEMETRY_ENABLED=false "$VENV/bin/reflex" run --backend-only --backend-port "$BP" --loglevel debug > "$LOG" 2>&1 &
PID=$!
for i in $(seq 1 90); do
  code=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' "http://localhost:$BP/ping" 2>/dev/null)
  [ "$code" = "200" ] && break
  sleep 1
done
: > "$OUT"
echo "backend_up_code=$code" >> "$OUT"
for p in /ping /admin /admin/ /admin/widget/list /admin/login /admin/statics/css/tabler.min.css /admin/api/widget; do
  c=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' -L "http://localhost:$BP$p")
  echo "$p -> $c" >> "$OUT"
done
curl -s --noproxy '*' "http://localhost:$BP/admin/" -o "$D/logs/admin_${LABEL}_index.html"
kill $PID 2>/dev/null
wait $PID 2>/dev/null
# clean up any orphan on the port
for pid in $(ss -lptn "sport = :$BP" 2>/dev/null | grep -oP 'pid=\K[0-9]+' | sort -u); do kill -9 "$pid" 2>/dev/null; done
cat "$OUT"
