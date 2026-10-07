#!/usr/bin/env bash
# Prod (single port 8341, Redis) run of the entauth suite.  Usage: prod_suite.sh <venv> <appdir> <label>
# Starts the mock IdP fresh BEFORE the app (the app caches the IdP JWKS for its lifetime).
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/ent_auth2
VENV=$1; APPD=$2; L=$3; B=http://localhost:8341
DRV="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 timeout 900 $SB/envs/driver/bin/python"
MCPDRV="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 timeout 900 $SB/envs/ent_auth2-drv/bin/python"
$W/scripts/stop_app.sh > /dev/null
$W/scripts/infra.sh restart-oidc 3600
redis-cli -p 8349 flushall > /dev/null
VENV=$VENV APP_DIR=$APPD APP_BP=8341 $W/scripts/start_app.sh prod $W/logs/entauth-prod-redis-$L.log
$W/scripts/wait_ready.sh $B/ $B 600 || exit 1
cd $W/scripts
echo "== drive_auth_redis"; $DRV drive_auth_redis.py $B $L cycle,pubnav,twotab,xtab > $W/logs/drive-auth-$L.out 2>&1; tail -n 1 $W/logs/drive-auth-$L.out
echo "== xtab x5"; $DRV xtab_probe.py $B $L-rep 5 2>&1 | tail -n 1
echo "== stale hash"; $DRV stale_hash_probe.py $B $L 2 > $W/logs/stalehash-$L.out 2>&1; tail -n 1 $W/logs/stalehash-$L.out
echo "== hydration token"; $DRV hydration_token_probe.py $B $L reload_writes,newtab_writes > $W/logs/hydtoken-$L.out 2>&1; tail -n 1 $W/logs/hydtoken-$L.out
echo "== bglive"; $DRV bglive_probe.py $B $L direct > $W/logs/bglive-$L.out 2>&1; cut -c1-400 $W/logs/bglive-$L.out
echo "== mcp oauth"; $MCPDRV check_mcp_oauth_redis.py $B $B $L > $W/logs/mcp-oauth-$L.out 2>&1; tail -c 600 $W/logs/mcp-oauth-$L.out
echo "== mcp anon"; $MCPDRV check_mcp_anon.py $B $L --rate > $W/logs/mcp-anon-$L.out 2>&1; tail -c 300 $W/logs/mcp-anon-$L.out
echo PROD_SUITE_DONE
