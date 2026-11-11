#!/usr/bin/env bash
# Launcher for the entauth / mapsapp explorer apps (exec'd by scripts/start_app.sh). Usage: run_app.sh <dev|prod> <logfile> [extra reflex args...]
# Env: VENV (default $ENT_NEW), APP_DIR (copy under $WORK/auth, default entauth), REDIS (default 1 -> redis :8629),
# APP_FP/APP_BP (dev 3620/8620; prod single port APP_BP default 8621), GRANIAN_WORKERS, AUTH_EXTRA_SCOPES, AUTH_MULTI, MCP_*.
set -u
. "$(dirname "$0")/../../lib.sh"; W=$WORK/auth
MODE=$1; LOG=$2; shift 2
VENV=${VENV:-$ENT_NEW}
APP_DIR=${APP_DIR:-entauth}
cd "$W/$APP_DIR" || exit 1
export CI=true REFLEX_TELEMETRY_ENABLED=false QA_EXPECT_VENV=$VENV
export OIDC_ISSUER_URI=http://localhost:8638 OIDC_CLIENT_ID=reflex-integration-test OIDC_CLIENT_SECRET=reflex-integration-test-secret AUTHLIB_INSECURE_TRANSPORT=1
if [ "${REDIS:-1}" = "1" ]; then export REFLEX_REDIS_URL=redis://localhost:8629; fi
if [ "${AUTH_MULTI:-}" = "1" ]; then
  export ACME_ISSUER_URI=http://localhost:8638 ACME_CLIENT_ID=reflex-integration-test GLOBEX_ISSUER_URI=http://localhost:8638 GLOBEX_CLIENT_ID=reflex-integration-test
fi
if [ "$MODE" = "prod" ]; then
  acct_stub
  P=${APP_BP:-8621}
  export APP_FP=$P APP_BP=$P REFLEX_API_URL=http://localhost:$P
  exec "$SB/envs/$VENV/bin/reflex" run --env prod --frontend-port $P --backend-port $P --loglevel debug "$@" > "$LOG" 2>&1
else
  FP=${APP_FP:-3620}; BP=${APP_BP:-8620}
  export APP_FP=$FP APP_BP=$BP
  exec "$SB/envs/$VENV/bin/reflex" run --frontend-port $FP --backend-port $BP --loglevel debug "$@" > "$LOG" 2>&1
fi
