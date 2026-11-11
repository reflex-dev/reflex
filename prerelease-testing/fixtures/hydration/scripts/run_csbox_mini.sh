#!/bin/bash
# Usage: run_csbox_mini.sh <venv> [FP_DEV=3152] [BP_DEV=8152] [FP_PROD=3141]
#   1. src/csbox dev + csbox_check.py: ComponentState + LocalStorage per-instance defaults (#7461 / N-005 / A3-03): fresh load
#      writes nothing, each box's choice persists into a new tab; instances with the same declared name share the key.
#   2. src/mini_writeback prod: mini_writeback_check.py (fresh profile writes nothing = F-002), restart with
#      MINI_THEME_DEFAULT=dark -> returning visitor who never chose sees dark; mini_choose.py (a user choice persists).
. "$(dirname "$0")/env.sh"
V=$1; FD=${2:-3152}; BD=${3:-8152}; FPP=${4:-3141}
O=$W/results/csbox_mini; mkdir -p "$O"
"$F/scripts/srv.sh" start "csbox-$V" "$V" dev "$F/src/csbox" "$FD" "$BD" > /dev/null || exit 1
$NP "$DRV" "$F/drivers/waitsrv.py" 400 "http://localhost:$FD/" "http://localhost:$BD/ping" > /dev/null && sleep 3 && \
  $NP timeout 600 "$DRV" "$F/drivers/csbox_check.py" "http://localhost:$FD" "$O/csbox_$V.json" 2>&1 | tail -8
"$F/scripts/srv.sh" stop "csbox-$V" > /dev/null
"$F/scripts/srv.sh" start "mini-$V" "$V" prod "$F/src/mini_writeback" "$FPP" "$FPP" > /dev/null || exit 1
$NP "$DRV" "$F/drivers/waitsrv.py" 400 "http://localhost:$FPP/" "http://localhost:$FPP/ping" > /dev/null && sleep 2
echo "== fresh"; $NP "$DRV" "$F/drivers/mini_writeback_check.py" "http://localhost:$FPP/" - "$O/mini_state_$V.json" 2>&1 | tail -4
echo "== choose"; $NP "$DRV" "$F/drivers/mini_choose.py" "http://localhost:$FPP/" "$O/mini_chosen_$V.json" 2>&1 | tail -4
"$F/scripts/srv.sh" stop "mini-$V" > /dev/null
"$F/scripts/srv.sh" start "mini-$V" "$V" prod "$F/src/mini_writeback" "$FPP" "$FPP" MINI_THEME_DEFAULT=dark > /dev/null || exit 1
$NP "$DRV" "$F/drivers/waitsrv.py" 400 "http://localhost:$FPP/" "http://localhost:$FPP/ping" > /dev/null && sleep 2
echo "== returning visitor after default -> dark"; $NP "$DRV" "$F/drivers/mini_writeback_check.py" "http://localhost:$FPP/" "$O/mini_state_$V.json" 2>&1 | tail -4
echo "== chosen user after default -> dark"; $NP "$DRV" "$F/drivers/mini_writeback_check.py" "http://localhost:$FPP/" "$O/mini_chosen_$V.json" 2>&1 | tail -4
"$F/scripts/srv.sh" stop "mini-$V" > /dev/null
