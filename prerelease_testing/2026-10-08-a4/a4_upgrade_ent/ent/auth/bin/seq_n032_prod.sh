#!/usr/bin/env bash
# N-032 verifier probes in PROD (single port 8621, Redis 8629, GRANIAN_WORKERS=1 as in the a3 pass), vauth app, <venv> <label>.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; E=$SB/apps/a4_upgrade_ent/ent/auth
V=${1:-a4-ent}; L=${2:-a4e}
DRV="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 timeout 900 $SB/envs/driver/bin/python"
$E/bin/infra.sh start; redis-cli -p 8629 flushall
GRANIAN_WORKERS=1 $E/bin/start_app.sh $V vauth_$L prod $E/logs/$L-prod-redis-1w.server.log
$E/bin/wait_ready.sh http://localhost:8621/ http://localhost:8621 600 || { $E/bin/stop_app.sh; $E/bin/infra.sh stop; exit 1; }
cd $E/drivers
for m in stale away xtab; do $DRV vdrv.py $m http://localhost:8621 $L-prod-redis-1w 3 2>&1 | grep SUMMARY | cut -c1-300; done
$DRV race.py ../logs/$L-prod-redis-1w-xtab.json 2>&1 | tail -n 3 | cut -c1-200
$DRV hunt.py loads http://localhost:8621 $L-prod-redis-1w 1 2>&1 | grep -E "SUMMARY" | cut -c1-200
$E/bin/stop_app.sh; $E/bin/infra.sh stop
echo "server log: tracebacks=$(grep -c Traceback $E/logs/$L-prod-redis-1w.server.log) TypeError=$(grep -c TypeError $E/logs/$L-prod-redis-1w.server.log)"
