#!/usr/bin/env bash
# usage: mcp_run.sh <venv> <label>  -- entauth dev + Redis: check_mcp_anon.py --rate and check_mcp_oauth_redis.py (clients on $ENT_DRV)
set -u
SB=${SB:?}; export WORK=$SB/apps/enterprise/work; F=$SB/apps/enterprise/src; . "$F/lib.sh"; fx_sync auth; E=$WORK/auth; B=$F/auth/bin
V=$1; L=$2; venv_check "$ENT_DRV" || exit 1
"$B/infra.sh" start; redis-cli -p 8629 flushall
fx_app auth entauth entauth_$L
VENV=$V APP_DIR=entauth_$L "$F/auth/scripts/start_app.sh" dev "$E/logs/entauth-mcp-$L.log"
"$B/wait_ready.sh" http://localhost:3620/ http://localhost:8620 420 || { "$B/stop_app.sh"; "$B/infra.sh" stop; exit 1; }
cd "$E/scripts"
$NP timeout 900 "$SB/envs/$ENT_DRV/bin/python" check_mcp_anon.py http://localhost:8620 $L --rate > "$E/logs/mcp-anon-$L.txt" 2>&1; echo "check_mcp_anon exit=$?"; tail -n 6 "$E/logs/mcp-anon-$L.txt" | cut -c1-300
$NP timeout 900 "$SB/envs/$ENT_DRV/bin/python" check_mcp_oauth_redis.py http://localhost:8620 http://localhost:3620 $L > "$E/logs/mcp-oauth-$L.txt" 2>&1; echo "check_mcp_oauth_redis exit=$?"; tail -n 6 "$E/logs/mcp-oauth-$L.txt" | cut -c1-300
"$B/stop_app.sh"; "$B/infra.sh" stop
echo "server log: tracebacks=$(grep -c Traceback "$E/logs/entauth-mcp-$L.log")"
