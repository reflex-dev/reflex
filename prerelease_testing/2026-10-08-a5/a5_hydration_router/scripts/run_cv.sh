#!/bin/bash
# Usage: run_cv.sh <venv> <dev|prod> <label> <FP> <BP> <variants|all> [ENV=VAL...]  -- cvstore + drive_cvstore.py (+ drive_cvnav.py when NAV=1)
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a5_hydration_router
V=$1; MODE=$2; L=$3; FP=$4; BP=$5; VARS=$6; shift 6
NP="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1"; DRV=$SB/envs/driver/bin/python
O=$W/results/f003; mkdir -p $O/frames
[ "$VARS" = all ] && VARS=""
$W/scripts/srv.sh start cv-$L $V $MODE $W/src/cvstore $FP $BP "$@" > /dev/null
$NP $DRV $W/drivers/waitsrv.py 400 http://localhost:$FP/ http://localhost:$BP/ping > /dev/null || { $W/scripts/srv.sh stop cv-$L; exit 1; }
sleep 3
cd $W/cv/drivers
$NP timeout 900 $DRV drive_cvstore.py http://localhost:$FP $O/frames $L $VARS > $O/$L.summary.txt 2>&1
grep -E "SUMMARY|FAIL|PASS" $O/$L.summary.txt | cut -c1-260
if [ "${NAV:-0}" = 1 ]; then $NP timeout 600 $DRV drive_cvnav.py http://localhost:$FP $L > $O/$L.cvnav.txt 2>&1; tail -12 $O/$L.cvnav.txt | cut -c1-200; fi
$W/scripts/srv.sh stop cv-$L > /dev/null
