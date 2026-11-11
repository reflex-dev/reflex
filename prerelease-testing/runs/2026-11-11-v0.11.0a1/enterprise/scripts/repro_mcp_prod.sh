#!/usr/bin/env bash
# Repro ISSUE 1: rxe MCPPlugin app under `reflex run --env prod` with deploy_url unset.
# Usage: repro_mcp_prod.sh <venv new-ent|prev-ent> <stub|token> [extra env, e.g. REFLEX_DEPLOY_URL=http://localhost:8381]
# Single port 8381; prints the readiness result, the ConfigError lines and the MCP issuer metadata.
set -u
SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad; E=$SB/apps/enterprise
V=$1; ACCT=$2; shift 2
R=$E/runs/mcpmin_${V//-/}; mkdir -p $R; (cd $E/src/mcpmin && tar --exclude=.web --exclude=__pycache__ -cf - .) | (cd $R && tar -xf -)
LOG=$E/logs/mcpmin_${V}_${ACCT}${1:+_extra}.log
if [ $ACCT = token ]; then A=(REFLEX_ACCESS_TOKEN="$(cat $SB/secrets/reflex_access_token)"); else
  curl -s --noproxy '*' -o /dev/null http://127.0.0.1:8397/ || $E/scripts/xc.sh stub
  A=(REFLEX_ACCESS_TOKEN=qa-fixture-token REFLEX_CLOUD_BACKEND_URL=http://127.0.0.1:8397); fi
cd $R; env CI=true REFLEX_TELEMETRY_ENABLED=false REFLEX_API_URL=http://localhost:8381 GRANIAN_WORKERS=1 "${A[@]}" "$@" \
  setsid $SB/envs/$V/bin/reflex run --env prod --frontend-port 8381 --backend-port 8381 > $LOG 2>&1 < /dev/null &
P=$!; sleep 1; G=$(ps -o pgid= -p $P | tr -d ' ')
for i in $(seq 1 120); do
  c=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' -m 3 http://localhost:8381/ping); [ "$c" = 200 ] && break
  kill -0 $P 2>/dev/null || break; sleep 2; done
echo "venv=$V acct=$ACCT extra=$* ping=$c alive=$(kill -0 $P 2>/dev/null && echo yes || echo no)"
grep -m2 "ConfigError" $LOG | cut -c1-220
curl -s --noproxy '*' -m 3 http://localhost:8381/.well-known/oauth-authorization-server | cut -c1-120; echo
kill -INT -- -$G 2>/dev/null; sleep 4; kill -KILL -- -$G 2>/dev/null; true
