#!/usr/bin/env bash
# The 10-05 a4 auth matrix (22 full-app cases + 3 reload + 4 default + 4 extra-scope + 3 iframe = 36) plus MCP OAuth and
# anonymous MCP, against <venv>. Dev mode, memory state manager. Servers run on <venv>, drivers on $ENT_DRV.
# Needs the upstream-derived pieces first: a4auth/fetch_upstream.sh (apps/auth + reference/ from a reflex-enterprise checkout).
# Usage: a4_matrix.sh <venv> <label>     (ports 3622/8622 auth, 3623/8623 auth_min, 8626 backend-only components)
. "$(dirname "$0")/../../lib.sh"; fx_sync auth; W=$WORK/auth; A=$W/a4auth; B=$FX/auth/bin
VENV=$1; L=$2
[ -d "$A/apps/auth" ] && [ -d "$A/reference" ] || { echo "run $FX/auth/a4auth/fetch_upstream.sh first"; exit 1; }
venv_check "$ENT_DRV" || exit 1
DRV="$NP timeout 1200 $SB/envs/$ENT_DRV/bin/python"
mkdir -p "$A/logs/$L" "$A/screenshots"
run_srv() {  # <appdir> <fp> <bp> <log> [extra env...]
  local app=$1 fp=$2 bp=$3 log=$4; shift 4
  "$B/stop_app.sh" > /dev/null
  (cd "$A/apps/$app" || exit 1; env "$@" CI=true REFLEX_TELEMETRY_ENABLED=false OIDC_ISSUER_URI=http://localhost:8638 \
     OIDC_CLIENT_ID=reflex-integration-test OIDC_CLIENT_SECRET=reflex-integration-test-secret AUTHLIB_INSECURE_TRANSPORT=1 \
     setsid "$SB/envs/$VENV/bin/reflex" run --frontend-port $fp --backend-port $bp --loglevel debug > "$log" 2>&1 < /dev/null &)
  sleep 1
  pgrep -f "envs/$VENV/bin/reflex run --frontend-port $fp" | head -1 | xargs -r ps -o pgid= -p | tr -d ' ' > "$W/run/app.pgid"
}
drive() {  # <app> <driver> <log-stem> <json> [env...]
  local app=$1 d=$2 stem=$3 js=$4; shift 4
  (cd "$A/apps/$app" && env "$@" $DRV ../../$d > "$A/logs/$L/$stem-driver.log" 2>&1); cp "$A/logs/$js" "$A/logs/$L/" 2>/dev/null; tail -n 2 "$A/logs/$L/$stem-driver.log"
}
"$B/infra.sh" restart-oidc 3600
run_srv auth 3622 8622 "$A/logs/$L/auth-full-server.log"   # full upstream app (extra_scopes address+offline_access)
"$B/wait_ready.sh" http://localhost:3622/ http://localhost:8622 600 || exit 1
drive auth drive_auth.py auth-full auth-full-browser.json
drive auth recheck_reload.py reload-repeat reload-repeat.json
run_srv auth_min 3623 8623 "$A/logs/$L/auth-min-default-server.log"
"$B/wait_ready.sh" http://localhost:3623/ http://localhost:8623 600 || exit 1
drive auth_min drive_auth_min.py auth-min-default auth-min-default-browser.json
drive auth_min recheck_iframe.py iframe-repeat iframe-repeat.json
drive auth_min check_mcp_oauth.py mcp-oauth mcp-oauth.json
run_srv auth_min 3623 8623 "$A/logs/$L/auth-min-extra-server.log" AUTH_TEST_EXTRA_SCOPES=1
"$B/wait_ready.sh" http://localhost:3623/ http://localhost:8623 600 || exit 1
drive auth_min drive_auth_min.py auth-min-extra auth-min-extra-browser.json AUTH_TEST_EXTRA_SCOPES=1
"$B/stop_app.sh" > /dev/null   # anonymous MCP: components app, backend only
(cd "$A/apps/components" || exit 1; env CI=true REFLEX_TELEMETRY_ENABLED=false setsid "$SB/envs/$VENV/bin/reflex" run --backend-only --backend-port 8626 --loglevel debug > "$A/logs/$L/mcp-anonymous-server.log" 2>&1 < /dev/null &)
sleep 1; pgrep -f "envs/$VENV/bin/reflex run --backend-only --backend-port 8626" | head -1 | xargs -r ps -o pgid= -p | tr -d ' ' > "$W/run/app.pgid"
for i in $(seq 1 300); do curl -s --noproxy '*' http://localhost:8626/ping | grep -q pong && break; sleep 1; done
drive components check_mcp.py mcp-anonymous mcp-anonymous.json
"$B/stop_app.sh" > /dev/null
echo A4_MATRIX_DONE
