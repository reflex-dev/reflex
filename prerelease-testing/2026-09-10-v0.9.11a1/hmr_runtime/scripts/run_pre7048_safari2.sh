#!/usr/bin/env bash
# Pre-#7048 sensitivity check, second pass: curl raw bytes + browser test (bodies saved even if the page never renders).
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
R=$SB/apps/hmr_runtime; S=$R/scripts; L=$R/logs; APP=$R/hmr_app_pre7048
export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
env -u NO_PROXY -u no_proxy $S/start_server.sh $SB/envs/hmr_pre7048 $APP 3104 8104 $L/dev_pre7048_2.log $L/dev_pre7048_2.pid || { echo START-FAILED; exit 1; }
sleep 2
$S/curl_safari.sh http://localhost:3104 $L/curl_safari_pre7048 > $L/curl_safari_pre7048.txt 2>&1; echo "curl pre7048 exit $?"
$SB/envs/driver/bin/python $S/safari_test.py --url http://localhost:3104 --out $L/safari_pre7048 --render-timeout 20 > $L/safari_pre7048_stdout.log 2>&1; echo "safari pre7048 exit $?"
$S/stop_server.sh $L/dev_pre7048_2.pid 3104 8104
echo PIPELINE-DONE
