#!/bin/bash
# Usage: run_h4.sh <venv> <dev|prod> <label> <FP> <BP> [only=C1,C2,..|-] [ENV=VAL...]
#   src/h4mix + drivers/h4_drive.py (Part 2 #7505 regression hunt). Output: results/h4/<label>.json/.txt, log logs/h4-<label>-<n>.log
. "$(dirname "$0")/env.sh"
V=$1; MODE=$2; L=$3; FP=$4; BP=$5; ONLY=${6:--}; shift 6 2>/dev/null || shift $#
[ "$ONLY" = "-" ] && ONLY=""
O=$W/results/h4; mkdir -p $O
RUN=$W/run/h4-$L
# reuse node_modules from a bootecho run dir of the same venv (saves the bun install)
if [ ! -d $RUN/.web ] && [ -d $W/run/st-$V-$MODE/.web ]; then mkdir -p $RUN && cp -a $W/run/st-$V-$MODE/.web $RUN/; fi
$F/scripts/srv.sh start h4-$L $V $MODE $F/src/h4mix $FP $BP "$@" || exit 1
$NP $DRV $F/drivers/waitsrv.py 500 http://localhost:$FP/ http://localhost:$BP/ping > /dev/null || { echo "server not up"; tail -30 $(ls -t $W/logs/h4-$L-*.log | head -1); $F/scripts/srv.sh stop h4-$L; exit 1; }
sleep 3
echo "state.js md5: $(md5sum < $RUN/.web/utils/state.js | cut -c1-8)"
(cd $W && $NP timeout 900 $DRV $F/drivers/h4_drive.py http://localhost:$FP $O/$L.json "$ONLY" > $O/$L.txt 2>&1)
tail -1 $O/$L.txt
$F/scripts/srv.sh stop h4-$L > /dev/null
LOG=$(ls -t $W/logs/h4-$L-*.log | head -1)
echo "server log: $LOG; error/traceback lines: $(grep -ciE 'traceback|error' $LOG)"
grep -iE 'traceback|error|exception' $LOG | grep -v 'Unexpected exit from worker' | sort | uniq -c | sort -rn | head -8
