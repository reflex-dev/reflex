#!/usr/bin/env bash
# Re-run the 10-05 a4 auth matrix (22 full-app cases + 3 reload + 4 default + 4 extra-scope + 3 iframe = 36)
# plus the a4 MCP OAuth / anonymous MCP checks, against <venv>.  Dev mode, memory state manager (as on 10-05).
# Usage: a4_matrix.sh <venv> <label>
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/a3_ent_auth
A=$W/a4auth
VENV=$1; L=$2
DRV="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 timeout 1200 $SB/envs/ent_auth2-drv/bin/python"
mkdir -p $A/logs/$L $A/screenshots
run_srv() {  # <appdir> <fp> <bp> <log> [extra env...]
  local app=$1 fp=$2 bp=$3 log=$4; shift 4
  $W/scripts/stop_app.sh > /dev/null
  (cd $A/apps/$app && env "$@" CI=true REFLEX_TELEMETRY_ENABLED=false OIDC_ISSUER_URI=http://localhost:8358 \
     OIDC_CLIENT_ID=reflex-integration-test OIDC_CLIENT_SECRET=reflex-integration-test-secret AUTHLIB_INSECURE_TRANSPORT=1 \
     setsid $SB/envs/$VENV/bin/reflex run --frontend-port $fp --backend-port $bp --loglevel debug > $log 2>&1 < /dev/null &)
  sleep 1
  pgrep -f "envs/$VENV/bin/reflex run --frontend-port $fp" | head -1 | xargs -r ps -o pgid= -p | tr -d ' ' > $W/run/app.pgid
}
$W/scripts/infra.sh restart-oidc 3600
# full upstream app (extra_scopes address+offline_access)
run_srv auth 3342 8342 $A/logs/$L/auth-full-server.log
$W/scripts/wait_ready.sh http://localhost:3342/ http://localhost:8342 600 || exit 1
(cd $A/apps/auth && $DRV ../../drive_auth.py > $A/logs/$L/auth-full-driver.log 2>&1); cp $A/logs/auth-full-browser.json $A/logs/$L/ 2>/dev/null; tail -n 2 $A/logs/$L/auth-full-driver.log
(cd $A/apps/auth && $DRV ../../recheck_reload.py > $A/logs/$L/reload-repeat-driver.log 2>&1); cp $A/logs/reload-repeat.json $A/logs/$L/ 2>/dev/null; tail -n 2 $A/logs/$L/reload-repeat-driver.log
# auth_min default
run_srv auth_min 3343 8343 $A/logs/$L/auth-min-default-server.log
$W/scripts/wait_ready.sh http://localhost:3343/ http://localhost:8343 600 || exit 1
(cd $A/apps/auth_min && $DRV ../../drive_auth_min.py > $A/logs/$L/auth-min-default-driver.log 2>&1); cp $A/logs/auth-min-default-browser.json $A/logs/$L/ 2>/dev/null; tail -n 2 $A/logs/$L/auth-min-default-driver.log
(cd $A/apps/auth_min && $DRV ../../recheck_iframe.py > $A/logs/$L/iframe-repeat-driver.log 2>&1); cp $A/logs/iframe-repeat.json $A/logs/$L/ 2>/dev/null; tail -n 2 $A/logs/$L/iframe-repeat-driver.log
(cd $A/apps/auth_min && $DRV ../../check_mcp_oauth.py > $A/logs/$L/mcp-oauth-driver.log 2>&1); cp $A/logs/mcp-oauth.json $A/logs/$L/ 2>/dev/null; tail -n 2 $A/logs/$L/mcp-oauth-driver.log
# auth_min extra scopes
run_srv auth_min 3343 8343 $A/logs/$L/auth-min-extra-server.log AUTH_TEST_EXTRA_SCOPES=1
$W/scripts/wait_ready.sh http://localhost:3343/ http://localhost:8343 600 || exit 1
(cd $A/apps/auth_min && AUTH_TEST_EXTRA_SCOPES=1 $DRV ../../drive_auth_min.py > $A/logs/$L/auth-min-extra-driver.log 2>&1); cp $A/logs/auth-min-extra-browser.json $A/logs/$L/ 2>/dev/null; tail -n 2 $A/logs/$L/auth-min-extra-driver.log
# anonymous MCP: components app, backend only
$W/scripts/stop_app.sh > /dev/null
(cd $A/apps/components && env CI=true REFLEX_TELEMETRY_ENABLED=false setsid $SB/envs/$VENV/bin/reflex run --backend-only --backend-port 8346 --loglevel debug > $A/logs/$L/mcp-anonymous-server.log 2>&1 < /dev/null &)
sleep 1; pgrep -f "envs/$VENV/bin/reflex run --backend-only --backend-port 8346" | head -1 | xargs -r ps -o pgid= -p | tr -d ' ' > $W/run/app.pgid
for i in $(seq 1 300); do curl -s --noproxy '*' http://localhost:8346/ping | grep -q pong && break; sleep 1; done
(cd $A/apps/components && $DRV ../../check_mcp.py > $A/logs/$L/mcp-anonymous-driver.log 2>&1); cp $A/logs/mcp-anonymous.json $A/logs/$L/ 2>/dev/null; tail -n 2 $A/logs/$L/mcp-anonymous-driver.log
$W/scripts/stop_app.sh > /dev/null
echo A4_MATRIX_DONE
