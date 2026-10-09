#!/bin/bash
# vmatrix.sh <venv> <dev|prod|prodredis> [RUNS_RAW=3] [RUNS_RESTORE=3]
# The A3-11 / A3-12 verifier scenarios through a 100 ms RTT latency proxy (50 ms each way), app src/vhsync:
#   raw CDP 3 restored background tabs + 1 click (A3-11), Playwright restore 7 tabs + 1 click (A3-11),
#   raw CDP 6 background tabs on /doc/d0..d5 (A3-12), dev only: 4 stamping tabs + a backend hot reload (A3-12).
#   dev:       app 3660/8660, proxy 8661 -> 8660 (backend only), REFLEX_API_URL=http://localhost:8661, driver -> 3660
#   prod:      app 3662 (one port), proxy 3663 -> 3662, REFLEX_API_URL=http://localhost:3663, driver -> 3663
#   prodredis: as prod + redis-server on $VREDIS_PORT (default 8669; REFLEX_REDIS_URL; granian multi-worker)
# Storm = >50 frames in the last 5 s window; vh/scripts/vtrigger.py tells whether the race was hit.
. "$(dirname "$0")/env.sh"
VE=$1; MODE=$2; NR=${3:-3}; NS=${4:-3}
NAME=vh-$VE-dev; [ "$MODE" != dev ] && NAME=vh-$VE-prod
if [ "$MODE" = dev ]; then
  "$F/scripts/lproxy.sh" start 8661 8660 50
  "$F/scripts/srv.sh" start "$NAME" "$VE" dev "$F/src/vhsync" 3660 8660 REFLEX_API_URL=http://localhost:8661
  $NP "$DRV" "$F/drivers/waitsrv.py" 400 http://localhost:3660/ http://localhost:8660/ping > /dev/null || { echo "server not up"; exit 1; }
  FP=3660
else
  EXTRA=""
  if [ "$MODE" = prodredis ]; then
    REDIS_PORT=${VREDIS_PORT:-8669}; redis_up || exit 1
    EXTRA=REFLEX_REDIS_URL=redis://localhost:$REDIS_PORT
  fi
  "$F/scripts/lproxy.sh" start 3663 3662 50
  "$F/scripts/srv.sh" start "$NAME" "$VE" prod "$F/src/vhsync" 3662 3662 REFLEX_API_URL=http://localhost:3663 $EXTRA
  $NP "$DRV" "$F/drivers/waitsrv.py" 500 http://localhost:3662/ http://localhost:3662/ping > /dev/null || { echo "server not up"; exit 1; }
  FP=3663
fi
sleep 4
T=${VE}${MODE}
"$F/vh/scripts/vraw.sh" "${T}_rtt100_raw3" "$NR" $FP 3 300 pick-red 200 10
"$F/vh/scripts/vrun.sh" "${T}_rtt100_restore7_st300_1click" "$NS" $FP restore 7 --stagger 300 --clicks pick-red@200 --observe 10
"$F/vh/scripts/vraw.sh" "${T}_rtt100_rawdocs6_st0" 2 $FP 6 0 docs 0 10
if [ "$MODE" = dev ]; then
  "$F/vh/scripts/vrun.sh" "${T}_docsrestart4" 2 $FP docs-restart 4 --restart-cmd "echo '# reload' >> $W/run/$NAME/vhsync/vhsync.py" --restart-wait 15
fi
"$F/scripts/srv.sh" stop "$NAME"
if [ "$MODE" = dev ]; then "$F/scripts/lproxy.sh" stop 8661; else "$F/scripts/lproxy.sh" stop 3663; fi
[ "$MODE" = prodredis ] && redis_down
$DRV "$F/vh/scripts/vtrigger.py" "$W/results/vh/${T}_"*.json | tail -20
true
