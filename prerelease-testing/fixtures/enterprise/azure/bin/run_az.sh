#!/usr/bin/env bash
# reflex-azure-auth flows against the mock IdP (auth/bin/infra.sh, :8638) on <venv> <label>: dev 3630/8630, prod 8631.
# Usage: run_az.sh <venv> <label> [modes=dev[,prod]]   (venv from bin/build_venv.sh)
. "$(dirname "$0")/../../lib.sh"; T=$WORK/azure; IB=$FX/auth/bin
V=$1; L=$2; MODES=${3:-dev}
mkdir -p "$T"/{logs,shots,run}; rm -rf "$T/drivers"; cp -r "$FX/azure/drivers" "$T/drivers"
R=$T/run/$L; mkdir -p "$R"; (cd "$FX/azure/src/azapp" && tar --exclude=.web --exclude=__pycache__ -cf - .) | (cd "$R" && tar -xf -)
venv_check "$V" || exit 1
"$IB/infra.sh" start > /dev/null
for m in ${MODES//,/ }; do
  cd "$R"
  if [ $m = dev ]; then FP=3630; BP=8630; ARGS=(); else FP=8631; BP=8631; ARGS=(--env prod); acct_stub; fi
  CI=true REFLEX_TELEMETRY_ENABLED=false QA_EXPECT_VENV=$V AZURE_ISSUER_URI=http://localhost:8638 AZURE_CLIENT_ID=az-client AZURE_CLIENT_SECRET=az-secret \
    REFLEX_API_URL=http://localhost:$BP AUTHLIB_INSECURE_TRANSPORT=1 \
    setsid "$SB/envs/$V/bin/reflex" run --frontend-port $FP --backend-port $BP --loglevel debug "${ARGS[@]}" > "$T/logs/az-$L-$m.server.log" 2>&1 < /dev/null &
  PID=$!; start=$(date +%s)
  until [ "$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:$FP/)" = 200 ] && [ "$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:$BP/ping)" = 200 ]; do
    kill -0 $PID 2>/dev/null || { echo "server died"; tail -20 "$T/logs/az-$L-$m.server.log"; break; }; [ $(( $(date +%s) - start )) -gt 420 ] && { echo TIMEOUT; break; }; sleep 3; done
  (cd "$T/drivers" && $NP timeout 300 "$DRVPY" drive_az.py http://localhost:$FP $L-$m 2>&1 | tail -3 | cut -c1-500)
  kill -INT -- -$PID 2>/dev/null; for i in $(seq 1 20); do kill -0 $PID 2>/dev/null || break; sleep 0.5; done; kill -KILL -- -$PID 2>/dev/null
  for p in $FP $BP; do for lp in $(lsof -nP -iTCP:$p -sTCP:LISTEN -t 2>/dev/null); do kill -KILL $lp; done; done
  echo "az-$L-$m server: tracebacks=$(grep -c Traceback "$T/logs/az-$L-$m.server.log") verification_failed=$(grep -c 'verification failed' "$T/logs/az-$L-$m.server.log")"
done
"$IB/infra.sh" stop > /dev/null; acct_stub_stop
