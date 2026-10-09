#!/bin/bash
# Usage: run_hyd.sh <venv> <dev|prod> <label> <FP> <BP> [only=s1,s5,...]
#   src/hydapp + drivers/hyd_driver.py: the s1-s13 hydration sweep (storage roundtrip, F-002 s1b, sync tabs, clear/remove,
#   int cookie 'abc' (s4 anomaly), s5 300k ok / 1.2 MB = F-008 reconnect storm, redirect/bg/raise/multi on_load, slow on_load
#   superseded (s6b), is_hydrated gate, defaults, dynamic/catch-all routes, click during on_load (s10), #7357 upload+nav (s11),
#   event list (s12), boot bytes (s13)). Results $W/results/hyd/<label>/; compare two runs: scripts/cmp_hyd.py <dirA> <dirB>.
. "$(dirname "$0")/env.sh"
V=$1; MODE=$2; L=$3; FP=$4; BP=$5; ONLY=${6:-}
"$F/scripts/srv.sh" start "hyd-$L" "$V" "$MODE" "$F/src/hydapp" "$FP" "$BP" || exit 1
$NP "$DRV" "$F/drivers/waitsrv.py" 500 "http://localhost:$FP/" "http://localhost:$BP/ping" > /dev/null || { echo "server not up"; "$F/scripts/srv.sh" stop "hyd-$L"; exit 1; }
sleep 3
$NP timeout 1500 "$DRV" "$F/drivers/hyd_driver.py" --base "http://localhost:$FP" --label "$L" --out "$W/results/hyd/$L" ${ONLY:+--only "$ONLY"} 2>&1 | tail -25
"$F/scripts/srv.sh" stop "hyd-$L"
# F-008 verdict: hyd_driver marks s5 "pass" when it ran; the storm shows in the 1.2 MB leg's websocket opens / hydrated flag
[ -f "$W/results/hyd/$L/s5.json" ] && "$DRV" -I -c "import json,sys; d=json.load(open(sys.argv[1])); print('F-008 s5 1.2MB: hydrated=%s ws_opens=%s (storm when not hydrated / opens >> 2); 300k hydrated=%s in %ss' % (d.get('1200000_hydrated'), d.get('1200000_ws_opens'), d.get('300000_hydrated'), d.get('300000_time_to_hydrated_s')))" "$W/results/hyd/$L/s5.json"
