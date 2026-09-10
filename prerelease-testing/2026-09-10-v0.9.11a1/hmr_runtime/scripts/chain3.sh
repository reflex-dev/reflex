#!/usr/bin/env bash
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
R=$SB/apps/hmr_runtime; S=$R/scripts; L=$R/logs
until grep -q "CHAIN2-DONE" $L/chain2.log 2>/dev/null; do sleep 5; done
cp $S/hmr_app_pristine.py $R/hmr_app/hmr_app/hmr_app.py
env -u NO_PROXY -u no_proxy $S/start_server.sh $SB/envs/smoke $R/hmr_app 3100 8100 $L/dev_curl.log $L/dev_curl.pid || { echo START-FAILED; exit 1; }
sleep 2
$S/curl_safari.sh http://localhost:3100 $L/curl_safari_new > $L/curl_safari_new.txt 2>&1
echo "curl new exit $?"
$S/stop_server.sh $L/dev_curl.pid 3100 8100
echo CHAIN3-DONE
