#!/usr/bin/env bash
# Baseline (0.9.10.post2) Safari cache-bust test with the head-meta version of the app (~70KB multibyte <meta>).
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
R=$SB/apps/hmr_runtime; S=$R/scripts; L=$R/logs; APP=$R/hmr_app_base
export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
cp $S/hmr_app_pristine.py $APP/hmr_app/hmr_app.py
rm -rf $APP/.states $APP/hmr_app/__pycache__
env -u NO_PROXY -u no_proxy $S/start_server.sh $SB/envs/base0910 $APP 3101 8101 $L/dev_base_safari.log $L/dev_base_safari.pid || { echo START-FAILED; exit 1; }
sleep 3
$SB/envs/driver/bin/python $S/safari_test.py --url http://localhost:3101 --out $L/safari_base_headmeta > $L/safari_base_headmeta_stdout.log 2>&1
echo "safari base headmeta exit $?"
$S/stop_server.sh $L/dev_base_safari.pid 3101 8101
echo PIPELINE-DONE
