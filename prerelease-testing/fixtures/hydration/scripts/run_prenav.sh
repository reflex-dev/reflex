#!/bin/bash
# Usage: run_prenav.sh <venv> <label> [FP=3148] [PROXYPORT=3149]
#   F-010 (pre-CONNECT client nav runs the LEFT page's on_load; LOW, pre-existing since 0.10.0a1) on src/hydapp prod:
#   1. prenav_test.py (socket held 2 s; /slow -> /other and /items/1 -> /items/2) + preconnect_click.py (click before connect)
#   2. restart with REFLEX_API_URL=proxy, upgrade_delay_proxy.py delays the websocket upgrade 800 ms, f6_natural.py:
#      /redir hijack (2 runs) and /items/1 -> /items/2 at click delay 0 and 300 ms. Results $W/results/f010/.
. "$(dirname "$0")/env.sh"
V=$1; L=$2; FP=${3:-3148}; PP=${4:-3149}
O=$W/results/f010; mkdir -p "$O"
"$F/scripts/srv.sh" start "pn-$L" "$V" prod "$F/src/hydapp" "$FP" "$FP" || exit 1
$NP "$DRV" "$F/drivers/waitsrv.py" 500 "http://localhost:$FP/" "http://localhost:$FP/ping" > /dev/null || { "$F/scripts/srv.sh" stop "pn-$L"; exit 1; }
sleep 3
$NP timeout 300 "$DRV" "$F/drivers/prenav_test.py" "http://localhost:$FP" "$L" "$O/prenav_$L.json" 2000 2>&1 | tail -6
$NP timeout 300 "$DRV" "$F/drivers/preconnect_click.py" "http://localhost:$FP" "$L" "$O/preconnect_$L.json" 2500 2>&1 | tail -4
"$F/scripts/srv.sh" stop "pn-$L"
"$F/scripts/srv.sh" start "pn-$L" "$V" prod "$F/src/hydapp" "$FP" "$FP" REFLEX_API_URL=http://localhost:$PP || exit 1
$NP "$DRV" "$F/drivers/waitsrv.py" 500 "http://localhost:$FP/" "http://localhost:$FP/ping" > /dev/null || { "$F/scripts/srv.sh" stop "pn-$L"; exit 1; }
"$F/scripts/proxy.sh" start "$PP" "$FP" 800 "proxy-$L-d800"
sleep 2
$NP timeout 300 "$DRV" "$F/drivers/f6_natural.py" "http://localhost:$PP" "$L-redir" "$O/f6redir_$L.json" 2 0 /redir "#nav-item2" "*" 2>&1 | $DRV "$F/scripts/summ.py" | tail -3
$NP timeout 300 "$DRV" "$F/drivers/f6_natural.py" "http://localhost:$PP" "$L-items" "$O/f6items_$L.json" 2 0,300 2>&1 | $DRV "$F/scripts/summ.py" | tail -5
"$F/scripts/proxy.sh" stop "$PP"
"$F/scripts/srv.sh" stop "pn-$L"
