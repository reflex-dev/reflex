#!/usr/bin/env bash
# Usage: run_app.sh <dev|prod> <logfile> [extra reflex args...]
# Env passthrough: VENV (default ent_auth), APP_DIR (default entauth), REDIS (default 1),
# GRANIAN_WORKERS, REFLEX_OPLOCK_ENABLED, AUTH_EXTRA_SCOPES, AUTH_MULTI, MCP_* ...
set -u
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/ent_auth2
MODE=$1; LOG=$2; shift 2
VENV=${VENV:-alpha2-ent}
APP_DIR=${APP_DIR:-entauth}
cd $W/$APP_DIR
export CI=true REFLEX_TELEMETRY_ENABLED=false
export OIDC_ISSUER_URI=http://localhost:8358 OIDC_CLIENT_ID=reflex-integration-test OIDC_CLIENT_SECRET=reflex-integration-test-secret AUTHLIB_INSECURE_TRANSPORT=1
if [ "${REDIS:-1}" = "1" ]; then export REFLEX_REDIS_URL=redis://localhost:8349; fi
if [ "${AUTH_MULTI:-}" = "1" ]; then
  export ACME_ISSUER_URI=http://localhost:8358 ACME_CLIENT_ID=reflex-integration-test GLOBEX_ISSUER_URI=http://localhost:8358 GLOBEX_CLIENT_ID=reflex-integration-test
fi
if [ "$MODE" = "prod" ]; then
  P=${APP_BP:-8341}
  export APP_FP=$P APP_BP=$P REFLEX_API_URL=http://localhost:$P
  exec $SB/envs/$VENV/bin/reflex run --env prod --frontend-port $P --backend-port $P --loglevel debug "$@" > $LOG 2>&1
else
  FP=${APP_FP:-3340}; BP=${APP_BP:-8340}
  export APP_FP=$FP APP_BP=$BP
  exec $SB/envs/$VENV/bin/reflex run --frontend-port $FP --backend-port $BP --loglevel debug "$@" > $LOG 2>&1
fi
