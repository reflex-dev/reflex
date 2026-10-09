#!/usr/bin/env bash
# hunt.py fresh (fresh anonymous browser writes no token hash / client-storage default: F-002 angle) on vauth, and
# storx.py (vauthx: protected LocalStorage(sync=True)/Cookie across reload / new tab / client nav: A3-10) — dev, Redis.
# Usage: seq_ent_extra.sh [venv] [label]
. "$(dirname "$0")/../../lib.sh"; fx_sync auth; E=$WORK/auth; B=$FX/auth/bin
V=${1:-$ENT_NEW}; L=${2:-new}
fx_app auth vauth vauth_$L
"$B/infra.sh" start; redis-cli -p 8629 flushall
"$B/start_app.sh" "$V" vauth_$L dev "$E/logs/$L-dev-redis-fresh.server.log"
"$B/wait_ready.sh" http://localhost:3620/ http://localhost:8620 420 && (cd "$E/drivers" && $NP timeout 900 "$DRVPY" hunt.py fresh http://localhost:3620 $L-dev-redis 2 2>&1 | tail -n 3 | cut -c1-400)
"$B/stop_app.sh"
"$B/run_storx.sh" "$V:$L-dev-redis"
tail -n 25 "$E/logs/$L-dev-redis-storx.out" | cut -c1-300
"$B/infra.sh" stop
echo "### ent extra done $(date +%T)"
