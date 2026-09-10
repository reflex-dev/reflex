#!/usr/bin/env bash
# Run 2 on reflex 0.9.11a1: pristine source, fresh state, HMR driver + Safari plugin test.
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
R=$SB/apps/hmr_runtime; S=$R/scripts; L=$R/logs
export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
$S/stop_server.sh $L/dev_run1.pid 3100 8100
cp $S/hmr_app_pristine.py $R/hmr_app/hmr_app/hmr_app.py
rm -rf $R/hmr_app/.states $R/hmr_app/hmr_app/__pycache__
env -u NO_PROXY -u no_proxy $S/start_server.sh $SB/envs/smoke $R/hmr_app 3100 8100 $L/dev_run2.log $L/dev_run2.pid || { echo START-FAILED; exit 1; }
sleep 3
$SB/envs/driver/bin/python $S/hmr_driver.py --url http://localhost:3100 --backend-port 8100 --app-file $R/hmr_app/hmr_app/hmr_app.py --web-dir $R/hmr_app/.web --out $L/hmr_new2 --label new2 > $L/hmr_new2_stdout.log 2>&1
echo "driver exit $?"
$SB/envs/driver/bin/python $S/safari_test.py --url http://localhost:3100 --out $L/safari_new > $L/safari_new_stdout.log 2>&1
echo "safari exit $?"
$S/stop_server.sh $L/dev_run2.pid 3100 8100
echo PIPELINE-DONE
