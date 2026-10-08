#!/bin/bash
# Usage: run_gauth.sh <venv> <dev|prod> <label> <FP> <BP> <seed> [full]  -- google_auth_demo + drive_gauth.py (+ drive_google_auth.py when 7th arg = full)
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a4_hydration
V=$1; MODE=$2; L=$3; FP=$4; BP=$5; S=$6; FULL=${7:-}
NP="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1"; DRV=$SB/envs/driver/bin/python
O=$W/results/gauth; mkdir -p $O
$W/scripts/srv.sh start ga-$L $V $MODE $W/src/google_auth_demo $FP $BP PYTHONHASHSEED=$S GOOGLE_CLIENT_ID=123456789012-dummyclientid.apps.googleusercontent.com > /dev/null
$NP $DRV $W/drivers/waitsrv.py 500 http://localhost:$FP/ http://localhost:$BP/ping > /dev/null || { $W/scripts/srv.sh stop ga-$L; exit 1; }
sleep 3
cd $W/cv/drivers
$NP timeout 600 $DRV drive_gauth.py http://localhost:$FP $O/$L.json $L 2>&1 | grep GAUTH | cut -c1-300
[ -n "$FULL" ] && { $NP timeout 900 $DRV drive_google_auth.py http://localhost:$FP $O/$L-full $L > $O/$L-full.txt 2>&1; tail -4 $O/$L-full.txt | cut -c1-300; }
$W/scripts/srv.sh stop ga-$L > /dev/null
