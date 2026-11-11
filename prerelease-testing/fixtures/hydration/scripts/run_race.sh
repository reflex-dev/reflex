#!/bin/bash
# Usage: run_race.sh <venv> <label> [FP=3660] [BP=8660] [RTT_PROXY_PORT|-] [REPS=3]
#   A4-03 (two tabs writing a sync=True LocalStorage var within ~1 RTT converge on the EARLIER write; LOW, by design) on
#   src/h4mix dev: b2b_probe.py alt (reporter's zero-gap alternation), race.py gap sweep + on_load + background-task races,
#   bootwin.py /norm boot window (O-2). With a 4th port arg, a latency proxy (50 ms each way = 100 ms RTT) is put in front
#   of the backend. Expected (0.10.0a4/a5): every run consistent (all tabs = localStorage = backend), 0 storms; the final
#   value may be the earlier write within one RTT. Results $W/results/race/.
. "$(dirname "$0")/env.sh"
V=$1; L=$2; FP=${3:-3660}; BP=${4:-8660}; PX=${5:--}; R=${6:-3}
O=$W/results/race; mkdir -p "$O"
EXTRA=()
if [ "$PX" != - ]; then "$F/scripts/lproxy.sh" start "$PX" "$BP" 50; EXTRA=(REFLEX_API_URL=http://localhost:$PX); fi
out=$("$F/scripts/srv.sh" start "h4r-$L" "$V" dev "$F/src/h4mix" "$FP" "$BP" "${EXTRA[@]}") || { echo "$out"; exit 1; }; echo "$out"
LOG=$(echo "$out" | sed -n 's/.*log=//p')
$NP "$DRV" "$F/drivers/waitsrv.py" 500 "http://localhost:$FP/" "http://localhost:$BP/ping" > /dev/null || { "$F/scripts/srv.sh" stop "h4r-$L"; exit 1; }
sleep 3
$NP timeout 600 "$DRV" "$F/drivers/b2b_probe.py" "http://localhost:$FP" "$O/${L}_b2b_alt.json" "$R" alt 2>&1 | tail -$((R+1))
$NP timeout 1200 "$DRV" "$F/drivers/race.py" "http://localhost:$FP" "$O/${L}_race.json" "$LOG" "$R" gap:0 gap:10 gap:40 gap:80 gap:150 pwalt onload:0 bg:570 2>&1 | tail -12
$NP timeout 900 "$DRV" "$F/drivers/bootwin.py" "http://localhost:$FP" "$O/${L}_bootwin_norm.json" "$LOG" /norm 0 2 4 6 8 10 2>&1 | tail -8
"$F/scripts/srv.sh" stop "h4r-$L"
[ "$PX" != - ] && "$F/scripts/lproxy.sh" stop "$PX"
true
