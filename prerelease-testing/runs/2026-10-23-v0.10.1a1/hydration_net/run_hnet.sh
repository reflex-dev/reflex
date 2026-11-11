#!/bin/bash
# Usage: run_hnet.sh <venv> <dev|prod> <label> <FP> <BP> [--proxy PP:mode] [--driver "args"] [--probe-only] [-- ENV=VAL...]
# Starts the hnet app (srv.sh, neutral run dir $WORK/run/hnet-<label>) with optional xff_proxy.py PP -> BP (the browser's
# websocket goes through it when --proxy is given: REFLEX_API_URL=http://localhost:PP). Runs probes/hnet_drive.py with
# --driver args against the frontend, then stops everything. --probe-only: start the server/proxy and leave them running
# (stop with: run_hnet.sh stop <label>).
SB=${SB:?}; export WORK=${WORK:-$SB/apps/hydration_net}
. "$WORK/src/scripts/env.sh"
P=$WORK/probes
if [ "$1" = stop ]; then
  "$F/scripts/srv.sh" stop "hnet-$2"; [ -f "$W/run/xffproxy-$2.pid" ] && { kill "$(cat "$W/run/xffproxy-$2.pid")" 2>/dev/null; rm -f "$W/run/xffproxy-$2.pid"; }
  exit 0
fi
V=$1; MODE=$2; L=$3; FP=$4; BP=$5; shift 5
PROXY=""; DARGS=""; PROBE_ONLY=""
while [ $# -gt 0 ] && [ "$1" != "--" ]; do
  case $1 in
    --proxy) PROXY=$2; shift 2;;
    --driver) DARGS=$2; shift 2;;
    --probe-only) PROBE_ONLY=1; shift;;
    *) echo "unknown $1"; exit 2;;
  esac
done
[ "${1:-}" = "--" ] && shift
API=""
if [ -n "$PROXY" ]; then
  PP=${PROXY%%:*}; PMODE=${PROXY#*:}; [ "$PMODE" = "$PROXY" ] && PMODE=append
  $DRV "$P/xff_proxy.py" "$PP" "$BP" --mode "$PMODE" > "$W/logs/xffproxy-$L.log" 2>&1 &
  echo $! > "$W/run/xffproxy-$L.pid"
  API="REFLEX_API_URL=http://localhost:$PP"
fi
"$F/scripts/srv.sh" start "hnet-$L" "$V" "$MODE" "$WORK/hnet" "$FP" "$BP" $API "$@" || exit 1
$NP "$DRV" "$F/drivers/waitsrv.py" 500 "http://localhost:$FP/" "http://localhost:$BP/ping" > /dev/null || { echo "server not up"; "$0" stop "$L"; exit 1; }
sleep 3
[ -n "$PROBE_ONLY" ] && { echo "left running: hnet-$L FP=$FP BP=$BP proxy=$PROXY"; exit 0; }
O=$W/results/hnet/$L; mkdir -p "$O"
if [ "$MODE" = prod ] && [ -n "$PROXY" ]; then FRONT=http://localhost:$PP; else FRONT=http://localhost:$FP; fi
$NP timeout 900 "$DRV" "$P/hnet_drive.py" --base "$FRONT" --out "$O" $DARGS 2>&1 | tee "$O/driver.txt" | grep -E "^\[|^SUMMARY"
"$0" stop "$L" > /dev/null
echo "log=$(ls -t "$W/logs/hnet-$L"-*.log | head -1)"
