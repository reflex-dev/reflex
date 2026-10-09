#!/usr/bin/env bash
# N-033: /_reflex/cookies/sync answers 405 on prod granian workers that have not served a page yet (default workers, Redis).
# Usage: seq_n033.sh [venv] [label]   -- vauth prod single port 8621 with VAUTH_PID_HEADER=1 (x-worker-pid header).
. "$(dirname "$0")/../../lib.sh"; fx_sync auth; E=$WORK/auth; B=$FX/auth/bin
V=${1:-$ENT_NEW}; L=${2:-new}
DRV="$NP timeout 900 $DRVPY"
fx_app auth vauth vauth_$L
"$B/infra.sh" start; redis-cli -p 8629 flushall
VAUTH_PID_HEADER=1 "$B/start_app.sh" "$V" vauth_$L prod "$E/logs/$L-prod-redis-dw.server.log"
"$B/wait_ready.sh" http://localhost:8621/ http://localhost:8621 600 || { "$B/stop_app.sh"; "$B/infra.sh" stop; exit 1; }
sleep 20
"$B/post_sync.sh" http://localhost:8621 27 "$E/logs/$L-prod-dw-post-fresh.txt"
(cd "$E/drivers" && $DRV vdrv.py logins http://localhost:8621 $L-prod-redis-dw 6 2>&1 | tail -n 3 | cut -c1-300)
"$B/post_sync.sh" http://localhost:8621 27 "$E/logs/$L-prod-dw-post-after-logins.txt"
(cd "$E/drivers" && $DRV vdrv.py storm http://localhost:8621 $L-prod-redis-dw 3 2>&1 | tail -n 3 | cut -c1-300)
"$B/stop_app.sh"; "$B/infra.sh" stop
echo "server log: tracebacks=$(grep -c Traceback "$E/logs/$L-prod-redis-dw.server.log") 405s=$(grep -c ' 405' "$E/logs/$L-prod-redis-dw.server.log")"
