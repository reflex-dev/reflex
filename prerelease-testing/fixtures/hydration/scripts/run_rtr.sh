#!/bin/bash
# Usage: run_rtr.sh <venv> <dev|prod> <label> <FP> <BP> <PROXYPORT> [driver flags...] [-- ENV=VAL...]
# Starts drivers/hdr_proxy.py PROXYPORT -> BP (injects credential headers into every request incl. the websocket
# upgrade) and src/rtr via srv.sh as rtr-<label> with REFLEX_API_URL pointing at the proxy; runs drivers/rtr_drive.py
# (dev: with a backend hot reload = reconnect; NORELOAD=1 skips it), stops everything.
#   dev:  run_rtr.sh $NEW dev new-dev 3142 8142 8143          (browser loads 3142, websocket via 8143 -> 8142)
#   prod: run_rtr.sh $NEW prod new-prod 3144 3144 3145        (browser loads 3145 -> 3144, one port)
. "$(dirname "$0")/env.sh"
V=$1; MODE=$2; L=$3; FP=$4; BP=$5; PP=$6; shift 6
DFLAGS=(); while [ $# -gt 0 ] && [ "$1" != "--" ]; do DFLAGS+=("$1"); shift; done; [ "${1:-}" = "--" ] && shift
O=$W/results/rtr; mkdir -p $O
$DRV $F/drivers/hdr_proxy.py $PP $BP > $W/logs/hdrproxy-$L.log 2>&1 &
PXPID=$!
$F/scripts/srv.sh start rtr-$L $V $MODE $F/src/rtr $FP $BP REFLEX_API_URL=http://localhost:$PP "$@" || { kill $PXPID; exit 1; }
$NP $DRV $F/drivers/waitsrv.py 500 http://localhost:$FP/ http://localhost:$BP/ping > /dev/null || { echo "server not up"; $F/scripts/srv.sh stop rtr-$L; kill $PXPID; exit 1; }
sleep 3
RF=(); [ "$MODE" = dev ] && [ -z "${NORELOAD:-}" ] && RF=(--reload-file $W/run/rtr-$L/rtr/rtr.py)
if [ "$MODE" = prod ]; then FRONT=http://localhost:$PP; else FRONT=http://localhost:$FP; fi
$NP timeout 600 $DRV $F/drivers/rtr_drive.py $FRONT http://localhost:$PP $O/$L.json "${RF[@]}" "${DFLAGS[@]}" > $O/$L.txt 2>&1
tail -4 $O/$L.txt | cut -c1-700
$F/scripts/srv.sh stop rtr-$L > /dev/null
kill $PXPID; wait $PXPID 2>/dev/null
tail -1 $W/logs/hdrproxy-$L.log
