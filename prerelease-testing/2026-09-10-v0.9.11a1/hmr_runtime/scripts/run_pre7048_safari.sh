#!/usr/bin/env bash
# Sensitivity check: run the Safari cache-bust test against reflex 0.9.10.post1 (published BEFORE PR #7048).
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
R=$SB/apps/hmr_runtime; S=$R/scripts; L=$R/logs; APP=$R/hmr_app_pre7048
export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
mkdir -p $APP/hmr_app; cp $R/hmr_app/rxconfig.py $APP/; cp $R/hmr_app/hmr_app/__init__.py $APP/hmr_app/; cp $S/hmr_app_pristine.py $APP/hmr_app/hmr_app.py
env -u NO_PROXY -u no_proxy $S/start_server.sh $SB/envs/hmr_pre7048 $APP 3104 8104 $L/dev_pre7048.log $L/dev_pre7048.pid || { echo START-FAILED; exit 1; }
sleep 3
$SB/envs/driver/bin/python $S/safari_test.py --url http://localhost:3104 --out $L/safari_pre7048 > $L/safari_pre7048_stdout.log 2>&1
echo "safari pre7048 exit $?"
$S/stop_server.sh $L/dev_pre7048.pid 3104 8104
echo PIPELINE-DONE
