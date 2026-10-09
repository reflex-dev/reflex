#!/bin/bash
# Usage: run_be.sh <venv> <dev|prod> <label> <FP> <BP> [ENV=VAL...] -- bootecho app + bootecho_check.py
. "$(dirname "$0")/env.sh"
V=$1; MODE=$2; L=$3; FP=$4; BP=$5; shift 5
O=$W/results/bootecho; mkdir -p $O; cd $O
NAME=be-$L
out=$($F/scripts/srv.sh start $NAME $V $MODE $F/src/bootecho $FP $BP "$@") || { echo "$out"; exit 1; }; echo "$out"
LOG=$(echo "$out" | sed -n 's/.*log=//p')
$NP $DRV $F/drivers/waitsrv.py 400 http://localhost:$FP/ http://localhost:$BP/ping || { $F/scripts/srv.sh stop $NAME; exit 1; }
sleep 4
$NP timeout 600 $DRV $F/drivers/bootecho_check.py http://localhost:$FP $LOG be_$L.json
$F/scripts/srv.sh stop $NAME
echo "LOG=$LOG"
