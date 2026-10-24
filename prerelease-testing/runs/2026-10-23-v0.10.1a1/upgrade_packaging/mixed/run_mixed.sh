#!/usr/bin/env bash
# Run the mixed-floor probe app under one venv (dev or prod) and drive it. Usage: run_mixed.sh <venv-name> <label> [dev|prod]
# Ports FP=3470 BP=8470 (prod: single port 3470). A fresh copy of the app per run (own .web), deleted afterwards.
set -u
: "${SB:?}"
V=$1; L=$2; MODE=${3:-dev}; FP=${FP:-3470}; BP=${BP:-8470}; APP=${APP:-mixedapp}; DRIVER=${DRIVER:-drive_mixed.py}
M=$SB/apps/upgrade_packaging/mixed; R=$M/run/$L; rm -rf "$R"; mkdir -p "$M/run" "$M/out" "$M/logs"; cp -r "$M/$APP" "$R"
export REFLEX_TELEMETRY_ENABLED=false QA_EXPECT_VENV=$V
cd "$R"
if [ $MODE = prod ]; then
  REFLEX_API_URL=http://localhost:$FP setsid "$SB/envs/$V/bin/reflex" run --env prod --frontend-port $FP --backend-port $FP --loglevel debug > "$M/logs/$L.server.log" 2>&1 < /dev/null & BP=$FP
else
  setsid "$SB/envs/$V/bin/reflex" run --frontend-port $FP --backend-port $BP --loglevel debug > "$M/logs/$L.server.log" 2>&1 < /dev/null &
fi
PID=$!; echo "started $L pid=$PID ($(date +%T))"
t0=$(date +%s)
while true; do
  fc=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' --max-time 5 http://localhost:$FP/); bc=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' --max-time 5 http://localhost:$BP/ping)
  [ "$fc" = 200 ] && [ "$bc" = 200 ] && { echo "UP after $(( $(date +%s) - t0 ))s"; break; }
  kill -0 $PID 2>/dev/null || { echo "SERVER DIED"; tail -30 "$M/logs/$L.server.log"; exit 1; }
  [ $(( $(date +%s) - t0 )) -gt 420 ] && { echo "TIMEOUT"; tail -30 "$M/logs/$L.server.log"; kill -KILL -- -$PID; exit 1; }
  sleep 3
done
cd "$M" && env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 timeout 600 "$SB/envs/driver/bin/python" "$M/$DRIVER" http://localhost:$FP "$M/out" "$L" 2>&1 | tee "$M/logs/$L.driver.log"
kill -TERM $PID 2>/dev/null; for i in $(seq 1 20); do kill -0 $PID 2>/dev/null || break; sleep 0.5; done; kill -KILL -- -$PID 2>/dev/null
for p in $FP $BP; do for pid in $(lsof -nP -iTCP:$p -sTCP:LISTEN -t 2>/dev/null | sort -u); do kill -KILL "$pid"; done; done
echo "--- $L server log: warnings/deprecations/errors"
grep -iE 'warn|deprecat|error|traceback|exception' "$M/logs/$L.server.log" | grep -v -E 'incorrect peer|npmmirror|react-error-boundary|errorBoundaries' | cut -c1-220 | sort | uniq -c | sort -rn | head -12
cp "$R/.web/package.json" "$M/out/$L.package.json" 2>/dev/null
rm -rf "$R/.web"
