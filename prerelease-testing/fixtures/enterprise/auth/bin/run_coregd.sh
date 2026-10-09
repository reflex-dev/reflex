#!/usr/bin/env bash
# Core-only get_delta-override fixture (coregd; no enterprise): reflex must call State.get_delta for the boot hydrate
# (GET_DELTA_SAW theme='bogus-boot' once + 'bogus-nav'). N-032's reflex-side mechanism. Usage: run_coregd.sh [venv=rel] [dev|prod]
. "$(dirname "$0")/../../lib.sh"; fx_sync auth; W=$WORK/auth; B=$FX/auth/bin
V=${1:-${PREV:-rel}}; M=${2:-dev}
fx_app auth coregd coregd_$V
if [ "$M" = prod ]; then PP=8627 NOREDIS=1 "$B/start_app.sh" "$V" coregd_$V prod "$W/logs/coregd-$V-$M.server.log"; U=http://localhost:8627; BE=$U
else FP=3627 BP=8627 NOREDIS=1 "$B/start_app.sh" "$V" coregd_$V dev "$W/logs/coregd-$V-$M.server.log"; U=http://localhost:3627; BE=http://localhost:8627; fi
"$B/wait_ready.sh" $U/ $BE 400 && (cd "$W/drivers" && $NP "$DRVPY" coregd_drv.py $U > "$W/logs/coregd-$V-$M.driver.out" 2>&1)
grep GET_DELTA_SAW "$W/logs/coregd-$V-$M.server.log"
"$B/stop_app.sh" > /dev/null
