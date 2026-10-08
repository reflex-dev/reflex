#!/usr/bin/env bash
# Extra #7505 checks on <venv>: hunt.py fresh (fresh anonymous browser writes no token hash / client-storage default; F-002 angle)
# on vauth, and storx.py (vauthx: protected LocalStorage(sync=True)/Cookie across reload / new tab / client nav; A3-10 context) — dev, Redis.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; E=$SB/apps/a4_upgrade_ent/ent/auth
V=${1:-a4-ent}; L=${2:-a4e}
DRV="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 timeout 900 $SB/envs/driver/bin/python"
$E/bin/infra.sh start; redis-cli -p 8629 flushall
$E/bin/start_app.sh $V vauth_$L dev $E/logs/$L-dev-redis-fresh.server.log
$E/bin/wait_ready.sh http://localhost:3620/ http://localhost:8620 420 && (cd $E/drivers && $DRV hunt.py fresh http://localhost:3620 $L-dev-redis 2 2>&1 | tail -n 3 | cut -c1-400)
$E/bin/stop_app.sh
$E/bin/run_storx.sh $V:vauthx_$L:$L-dev-redis
tail -n 25 $E/logs/$L-dev-redis-storx.out | cut -c1-300
$E/bin/infra.sh stop
echo "### ent extra done $(date +%T)"
