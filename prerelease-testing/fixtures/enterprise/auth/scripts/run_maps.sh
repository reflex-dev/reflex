#!/usr/bin/env bash
# Enterprise maps app (mapsapp + drive_maps.py, 17 checks): dev 3624/8624 then prod 8625 (default workers), Redis.
# Usage: run_maps.sh [venv] [label]   (starts/stops bin/infra.sh itself)
. "$(dirname "$0")/../../lib.sh"; fx_sync auth; W=$WORK/auth; B=$FX/auth/bin
V=${1:-$ENT_NEW}; L=${2:-new}
fx_app auth mapsapp mapsapp_$L
"$B/infra.sh" start > /dev/null; redis-cli -p 8629 flushall > /dev/null
VENV=$V APP_DIR=mapsapp_$L APP_FP=3624 APP_BP=8624 "$FX/auth/scripts/start_app.sh" dev "$W/logs/maps-dev-redis-$L.log"
"$B/wait_ready.sh" http://localhost:3624/ http://localhost:8624 400 && (cd "$W/scripts" && $NP timeout 900 "$DRVPY" drive_maps.py http://localhost:3624 $L-dev-redis > "$W/logs/maps-$L-dev-redis.out" 2>&1; tail -n 3 "$W/logs/maps-$L-dev-redis.out")
"$B/stop_app.sh" > /dev/null
VENV=$V APP_DIR=mapsapp_$L APP_BP=8625 "$FX/auth/scripts/start_app.sh" prod "$W/logs/maps-prod-redis-$L.log"
"$B/wait_ready.sh" http://localhost:8625/ http://localhost:8625 600 && (cd "$W/scripts" && $NP timeout 900 "$DRVPY" drive_maps.py http://localhost:8625 $L-prod-redis > "$W/logs/maps-$L-prod-redis.out" 2>&1; tail -n 3 "$W/logs/maps-$L-prod-redis.out")
"$B/stop_app.sh" > /dev/null; "$B/infra.sh" stop > /dev/null
