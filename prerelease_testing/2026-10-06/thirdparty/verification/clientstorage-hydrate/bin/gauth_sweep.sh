#!/bin/bash
# Usage: gauth_sweep.sh <galpha|gstable> <fp> <bp> <seed>...  -- google demo dev server per seed + drive_gauth.py
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/verify_thirdparty_1
V=$1; FP=$2; BP=$3; shift 3
VENV=verify_thirdparty_1-$V
PIDF=$W/pids/google_auth_demo-$VENV.pid
export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
for s in "$@"; do
  GOOGLE_CLIENT_ID=123456789012-dummyclientid.apps.googleusercontent.com PYTHONHASHSEED=$s $W/start.sh $VENV $W/apps/$V/google_auth_demo $FP $BP $W/logs/gauth-$V-dev-seed$s.log > /dev/null
  $W/wait_up.sh http://localhost:$FP/ 500 $PIDF > /dev/null || { echo "seed $s: not up"; $W/stop.sh $PIDF; continue; }
  sleep 3
  (cd $W/drivers && $SB/envs/driver/bin/python drive_gauth.py http://localhost:$FP $W/out/gauth/gauth-$V-dev-seed$s.json $V-seed$s 2>&1 | tail -1)
  echo "   server 'Error verifying token' lines: $(grep -c 'Error verifying token' $W/logs/gauth-$V-dev-seed$s.log)"
  $W/stop.sh $PIDF > /dev/null; sleep 1
done
