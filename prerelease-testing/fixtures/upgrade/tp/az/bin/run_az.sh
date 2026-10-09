#!/usr/bin/env bash
# reflex-azure-auth flows (drivers/drive_az.py: A anonymous deep link -> on_load chain -> IdP -> callback -> back with the query,
# B login button, C signed-in client nav) on <venv> <label> [modes dev,prod]; dev 3463/8463, prod 8467.
# Needs the mock OIDC IdP (oidc-provider-mock) on IDP_URL (default http://localhost:8638): IDP_INFRA=<path to an infra.sh with
# start|stop> starts/stops it (the enterprise area's ent auth infra.sh), otherwise it must already be running.
# Needs CI=true (reflex-enterprise dev login gate). Expected (a5 and a4, dev + prod): A/B/C pass; prod returns to /protected/?x=1&y=two.
set -u; . "$(dirname "$0")/../../../bin/env.sh"; T=$(cd "$(dirname "$0")/.." && pwd)
V=$1; L=$2; MODES=${3:-dev}; IDP_URL=${IDP_URL:-http://localhost:8638}
R=$T/run/$L; mkdir -p "$T/run" "$T/logs"; [ -d "$R" ] || cp -r "$T/src/azapp" "$R"
[ -n "${IDP_INFRA:-}" ] && "$IDP_INFRA" start > /dev/null
[ "$(http_code $IDP_URL/.well-known/openid-configuration)" = 200 ] || { echo "no mock IdP at $IDP_URL (set IDP_INFRA)"; exit 2; }
for m in ${MODES//,/ }; do
  cd "$R"
  if [ $m = dev ]; then FP=3463; BP=8463; ARGS=(); else FP=8467; BP=8467; ARGS=(--env prod); fi
  CI=true QA_EXPECT_VENV=$V AZURE_ISSUER_URI=$IDP_URL AZURE_CLIENT_ID=az-client AZURE_CLIENT_SECRET=az-secret \
    REFLEX_API_URL=$([ $m = dev ] && echo http://localhost:$BP || echo http://localhost:$FP) AUTHLIB_INSECURE_TRANSPORT=1 \
    setsid "$SB/envs/$V/bin/reflex" run --frontend-port $FP --backend-port $BP --loglevel debug "${ARGS[@]}" > "$T/logs/az-$L-$m.server.log" 2>&1 < /dev/null &
  PID=$!; start=$(date +%s)
  until [ "$(http_code http://localhost:$FP/)" = 200 ] && [ "$(http_code http://localhost:$BP/ping)" = 200 ]; do
    kill -0 $PID 2>/dev/null || { echo "server died"; tail -20 "$T/logs/az-$L-$m.server.log"; break; }; [ $(( $(date +%s) - start )) -gt 420 ] && { echo TIMEOUT; break; }; sleep 3; done
  (cd "$T/drivers" && $DRV drive_az.py http://localhost:$FP $L-$m 2>&1 | tail -3 | cut -c1-500)
  kill -INT -- -$PID 2>/dev/null; for i in $(seq 1 20); do kill -0 $PID 2>/dev/null || break; sleep 0.5; done; kill -KILL -- -$PID 2>/dev/null
  for p in $FP $BP; do for lp in $(lsof -nP -iTCP:$p -sTCP:LISTEN -t 2>/dev/null); do kill -KILL $lp; done; done
  echo "az-$L-$m server: tracebacks=$(grep -c Traceback "$T/logs/az-$L-$m.server.log") verification_failed=$(grep -c 'verification failed' "$T/logs/az-$L-$m.server.log")"
done
[ -n "${IDP_INFRA:-}" ] && "$IDP_INFRA" stop > /dev/null
exit 0
