#!/usr/bin/env bash
# usage: mcp_oauth_mem.sh <venv> <label>  -- entauth dev WITHOUT Redis (memory state manager): does check_mcp_oauth_redis.py's consent flow pass?
set -u
SB=${SB:?}; export WORK=$SB/apps/enterprise/work; F=$SB/apps/enterprise/src; . "$F/lib.sh"; fx_sync auth; E=$WORK/auth; B=$F/auth/bin
V=$1; L=$2; venv_check "$ENT_DRV" || exit 1
"$B/infra.sh" start
fx_app auth entauth entauth_$L
REDIS=0 VENV=$V APP_DIR=entauth_$L "$F/auth/scripts/start_app.sh" dev "$E/logs/entauth-mcpmem-$L.log"
"$B/wait_ready.sh" http://localhost:3620/ http://localhost:8620 420 || { "$B/stop_app.sh"; "$B/infra.sh" stop; exit 1; }
cd "$E/scripts"
$NP timeout 900 "$SB/envs/$ENT_DRV/bin/python" check_mcp_oauth_redis.py http://localhost:8620 http://localhost:3620 $L-mem > "$E/logs/mcp-oauth-$L-mem.txt" 2>&1; echo "check_mcp_oauth_redis (memory) exit=$?"; tail -n 4 "$E/logs/mcp-oauth-$L-mem.txt" | cut -c1-300
"$B/stop_app.sh"; "$B/infra.sh" stop
grep -n "redirecting to\|Auth callback" "$E/logs/entauth-mcpmem-$L.log" | cut -c1-160 | head -4
