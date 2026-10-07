#!/usr/bin/env bash
# Run xtab_probe N times against each venv/app copy sequentially (one server at a time).
# Usage: xtab_matrix.sh <N> <venv:appdir:label> ...
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/a3_ent_auth
N=$1; shift
for spec in "$@"; do
  IFS=: read VENV APPD LABEL <<< "$spec"
  $W/scripts/stop_app.sh > /dev/null
  redis-cli -p 8349 flushall > /dev/null
  VENV=$VENV APP_DIR=$APPD $W/scripts/start_app.sh dev $W/logs/entauth-dev-redis-$LABEL.log
  $W/scripts/wait_ready.sh http://localhost:3340/ http://localhost:8340 || continue
  sleep 3
  (cd $W/scripts && NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 timeout 1200 $SB/envs/driver/bin/python xtab_probe.py http://localhost:3340 $LABEL-rep $N 2>&1 | tail -n $((N+1)))
done
$W/scripts/stop_app.sh > /dev/null
