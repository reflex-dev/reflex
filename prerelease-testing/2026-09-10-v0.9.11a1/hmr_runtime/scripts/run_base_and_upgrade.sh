#!/usr/bin/env bash
# Baseline (reflex 0.9.10.post2) run of the same app in hmr_app_base on ports 3101/8101:
#   HMR driver, Safari plugin test, double-edit probe -- then stop and re-run the SAME directory
#   under 0.9.11a1 (ports 3102/8102) to exercise the upgrade path (stale utils/context.js removal).
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
R=$SB/apps/hmr_runtime; S=$R/scripts; L=$R/logs; APP=$R/hmr_app_base
DRV=/home/user/reflex/.claude/skills/prerelease-test/scripts/drive_app.py
export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
cp $S/hmr_app_pristine.py $APP/hmr_app/hmr_app.py
rm -rf $APP/.states $APP/hmr_app/__pycache__

echo "=== BASELINE 0.9.10.post2"
env -u NO_PROXY -u no_proxy $S/start_server.sh $SB/envs/base0910 $APP 3101 8101 $L/dev_base.log $L/dev_base.pid || { echo START-FAILED; exit 1; }
sleep 3
echo "--- .web/utils under baseline:"; ls $APP/.web/utils/ | tee $L/upgrade_web_utils_before.txt
$SB/envs/driver/bin/python $S/hmr_driver.py --url http://localhost:3101 --backend-port 8101 --app-file $APP/hmr_app/hmr_app.py --web-dir $APP/.web --out $L/hmr_base --label base > $L/hmr_base_stdout.log 2>&1
echo "driver exit $?"
$SB/envs/driver/bin/python $S/safari_test.py --url http://localhost:3101 --out $L/safari_base > $L/safari_base_stdout.log 2>&1
echo "safari exit $?"
$SB/envs/driver/bin/python $S/double_edit_probe.py --app-file $APP/hmr_app/hmr_app.py --web-dir $APP/.web --server-log $L/dev_base.log --gaps 0.3,0.5,1.0 --out $L/double_probe_base.json > $L/double_probe_base_stdout.log 2>&1
echo "probe exit $?"
$S/stop_server.sh $L/dev_base.pid 3101 8101
cp $S/hmr_app_pristine.py $APP/hmr_app/hmr_app.py
ls -la $APP/.web/utils/ > $L/upgrade_web_utils_after_baseline_stop.txt

echo "=== UPGRADE: same dir under 0.9.11a1"
env -u NO_PROXY -u no_proxy $S/start_server.sh $SB/envs/smoke $APP 3102 8102 $L/dev_upgrade.log $L/dev_upgrade.pid || { echo UPGRADE-START-FAILED; tail -40 $L/dev_upgrade.log; exit 1; }
sleep 3
echo "--- .web/utils after upgrade:"; ls -la $APP/.web/utils/ | tee $L/upgrade_web_utils_after.txt
$SB/envs/driver/bin/python $DRV http://localhost:3102/ --screenshot $L/upgrade_index.png --report $L/upgrade_index.json \
  --actions '[{"click": "#inc-btn"}, {"click": "#inc-btn"}, {"wait": 800}, {"expect_text": "Counter: 2"}, {"click": "#cs-btn"}, {"expect_text": "client: cs-changed"}, {"click": "#toggle-btn"}, {"wait": 600}, {"expect_text": "Toggle: ON"}, {"goto": "http://localhost:3102/about"}, {"expect_text": "About"}, {"goto": "http://localhost:3102/long"}, {"wait": 500}, {"expect_text": "END OF LONG PAGE"}]' > $L/upgrade_drive_stdout.log 2>&1
echo "upgrade drive exit $?"
# one hot edit after upgrade to make sure HMR works in the upgraded dir
$SB/envs/driver/bin/python $S/hmr_driver.py --url http://localhost:3102 --backend-port 8102 --app-file $APP/hmr_app/hmr_app.py --web-dir $APP/.web --out $L/hmr_upgrade --label upgrade --steps text,default > $L/hmr_upgrade_stdout.log 2>&1
echo "upgrade driver exit $?"
$S/stop_server.sh $L/dev_upgrade.pid 3102 8102
echo PIPELINE-DONE
