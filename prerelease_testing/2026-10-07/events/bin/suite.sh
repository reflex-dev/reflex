#!/bin/bash
# Usage: suite.sh <label> <base_url> <backend_port> [groups]
# Runs the Playwright suite against a running evapp; report -> out/<label>/<label>_report.json
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/events2
L=$1; BASE=$2; BPORT=$3; G=${4:-sup,nested,thr,thr:PROXY,vars,typelog,api,bind,priv}
mkdir -p $W/out/$L
cd $W/driver
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 EV_BACKEND_PORT=$BPORT EV_SERVER_LOG=$W/logs/$L.log \
  EV_PROXY_STATE=$W/pids/$L.proxystate $SB/envs/driver/bin/python run_suite.py "$BASE" $W/out/$L $L "$G" 2>&1 | tee $W/out/$L/${L}_suite.txt
