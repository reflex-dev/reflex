#!/usr/bin/env bash
# Prod (single port 8621, Redis) run of the entauth suite + bglive (N-034) + MCP. Usage: prod_suite.sh <venv> <label>
# (old form prod_suite.sh <venv> <appdir> <label> still works). Starts the mock IdP fresh BEFORE the app (JWKS cached).
# GRANIAN_WORKERS passes through (the a3 pass used 1). MCP clients run on $ENT_DRV.
. "$(dirname "$0")/../../lib.sh"; fx_sync auth; W=$WORK/auth; B=$FX/auth/bin
VENV=$1; if [ $# -ge 3 ]; then APPD=$2; L=$3; else L=$2; APPD=entauth_$L; fi; U=http://localhost:8621
DRV="$NP timeout 900 $DRVPY"
MCPDRV="$NP timeout 900 $SB/envs/$ENT_DRV/bin/python"
fx_app auth entauth "$APPD"
"$B/stop_app.sh" > /dev/null
"$B/infra.sh" restart-oidc 3600
redis-cli -p 8629 flushall > /dev/null
VENV=$VENV APP_DIR=$APPD APP_BP=8621 "$FX/auth/scripts/start_app.sh" prod "$W/logs/entauth-prod-redis-$L.log"
"$B/wait_ready.sh" $U/ $U 600 || exit 1
cd "$W/scripts"
echo "== drive_auth_redis"; $DRV drive_auth_redis.py $U $L cycle,pubnav,twotab,xtab > "$W/logs/drive-auth-$L.out" 2>&1; tail -n 1 "$W/logs/drive-auth-$L.out"
echo "== xtab x5"; $DRV xtab_probe.py $U $L-rep 5 2>&1 | tail -n 1
echo "== stale hash"; $DRV stale_hash_probe.py $U $L 2 > "$W/logs/stalehash-$L.out" 2>&1; tail -n 1 "$W/logs/stalehash-$L.out"
echo "== hydration token"; $DRV hydration_token_probe.py $U $L reload_writes,newtab_writes > "$W/logs/hydtoken-$L.out" 2>&1; tail -n 1 "$W/logs/hydtoken-$L.out"
echo "== bglive"; $DRV bglive_probe.py $U $L direct > "$W/logs/bglive-$L.out" 2>&1; cut -c1-400 "$W/logs/bglive-$L.out"
echo "== mcp oauth"; $MCPDRV check_mcp_oauth_redis.py $U $U $L > "$W/logs/mcp-oauth-$L.out" 2>&1; tail -c 600 "$W/logs/mcp-oauth-$L.out"
echo "== mcp anon"; $MCPDRV check_mcp_anon.py $U $L --rate > "$W/logs/mcp-anon-$L.out" 2>&1; tail -c 300 "$W/logs/mcp-anon-$L.out"
"$B/stop_app.sh" > /dev/null
echo PROD_SUITE_DONE
