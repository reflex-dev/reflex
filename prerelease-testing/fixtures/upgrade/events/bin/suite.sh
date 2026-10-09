#!/bin/bash
# Usage: suite.sh <label> <base_url> <backend_port> [groups] [only_test_fns]
# Runs the Playwright suite against a running evapp; report -> out/<label>/<label>_report.json
. "$(dirname "$0")/../../bin/env.sh"
W=$(cd "$(dirname "$0")/.." && pwd)
L=$1; BASE=$2; BPORT=$3; G=${4:-sup,nested,thr,thr:PROXY,vars,typelog,api,bind,priv}; ONLY=${5:-}
mkdir -p $W/out/$L
cd $W/driver
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 EV_BACKEND_PORT=$BPORT EV_SERVER_LOG=$W/logs/$L.log \
  EV_PROXY_STATE=$W/pids/$L.proxystate $DPY run_suite.py "$BASE" $W/out/$L $L "$G" $ONLY 2>&1 | tee $W/out/$L/${L}_suite.txt
