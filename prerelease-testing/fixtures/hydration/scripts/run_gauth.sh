#!/bin/bash
# Usage: run_gauth.sh <venv> <dev|prod> <label> <FP> <BP> <seed> [full]  -- google_auth_demo + drive_gauth.py (+ drive_google_auth.py when 7th arg = full)
. "$(dirname "$0")/env.sh"
V=$1; MODE=$2; L=$3; FP=$4; BP=$5; S=$6; FULL=${7:-}
O=$W/results/gauth; mkdir -p $O
$F/scripts/srv.sh start ga-$L $V $MODE $F/src/google_auth_demo $FP $BP PYTHONHASHSEED=$S GOOGLE_CLIENT_ID=123456789012-dummyclientid.apps.googleusercontent.com > /dev/null || exit 1
$NP $DRV $F/drivers/waitsrv.py 500 http://localhost:$FP/ http://localhost:$BP/ping > /dev/null || { $F/scripts/srv.sh stop ga-$L; exit 1; }
sleep 3
cd $W
$NP timeout 600 $DRV $F/drivers/tp/drive_gauth.py http://localhost:$FP $O/$L.json $L 2>&1 | grep GAUTH | cut -c1-300
[ -n "$FULL" ] && { $NP timeout 900 $DRV $F/drivers/tp/drive_google_auth.py http://localhost:$FP $O/$L-full $L > $O/$L-full.txt 2>&1; tail -4 $O/$L-full.txt | cut -c1-300; }
$F/scripts/srv.sh stop ga-$L > /dev/null
