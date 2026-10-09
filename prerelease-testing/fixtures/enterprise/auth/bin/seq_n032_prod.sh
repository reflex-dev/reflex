#!/usr/bin/env bash
# N-032 verifier probes in PROD (vauth, single port 8621, Redis 8629, GRANIAN_WORKERS=1). Usage: seq_n032_prod.sh [venv] [label]
. "$(dirname "$0")/../../lib.sh"; fx_sync auth; E=$WORK/auth; B=$FX/auth/bin
V=${1:-$ENT_NEW}; L=${2:-new}
DRV="$NP timeout 900 $DRVPY"
fx_app auth vauth vauth_$L
"$B/infra.sh" start; redis-cli -p 8629 flushall
GRANIAN_WORKERS=1 "$B/start_app.sh" "$V" vauth_$L prod "$E/logs/$L-prod-redis-1w.server.log"
"$B/wait_ready.sh" http://localhost:8621/ http://localhost:8621 600 || { "$B/stop_app.sh"; "$B/infra.sh" stop; exit 1; }
cd "$E/drivers"
for m in stale away xtab; do $DRV vdrv.py $m http://localhost:8621 $L-prod-redis-1w 3 2>&1 | grep SUMMARY | cut -c1-300; done
$DRV race.py ../logs/$L-prod-redis-1w-xtab.json 2>&1 | tail -n 3 | cut -c1-200
$DRV hunt.py loads http://localhost:8621 $L-prod-redis-1w 1 2>&1 | grep -E "SUMMARY" | cut -c1-200
"$B/stop_app.sh"; "$B/infra.sh" stop
echo "server log: tracebacks=$(grep -c Traceback "$E/logs/$L-prod-redis-1w.server.log") TypeError=$(grep -c TypeError "$E/logs/$L-prod-redis-1w.server.log")"
