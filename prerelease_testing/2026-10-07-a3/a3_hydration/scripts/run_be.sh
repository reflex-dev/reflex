#!/bin/bash
# Usage: run_be.sh <venv> <dev|prod> <label> <FP> <BP> [ENV=VAL...] -- bootecho app + bootecho_check.py
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a3_hydration
V=$1; MODE=$2; L=$3; FP=$4; BP=$5; shift 5
NP="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1"; DRV=$SB/envs/driver/bin/python
O=$W/results/bootecho; mkdir -p $O; cd $O
NAME=be-$L
out=$($W/scripts/srv.sh start $NAME $V $MODE $W/src/bootecho $FP $BP "$@"); echo "$out"
LOG=$(echo "$out" | sed -n 's/.*log=//p')
$NP $DRV $W/drivers/waitsrv.py 400 http://localhost:$FP/ http://localhost:$BP/ping || { $W/scripts/srv.sh stop $NAME; exit 1; }
sleep 4
$NP timeout 600 $DRV $W/drivers/bootecho_check.py http://localhost:$FP $LOG be_$L.json
$W/scripts/srv.sh stop $NAME
echo "LOG=$LOG"
