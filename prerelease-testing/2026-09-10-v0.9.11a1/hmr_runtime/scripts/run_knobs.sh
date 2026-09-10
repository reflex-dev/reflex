#!/usr/bin/env bash
# Dev-server knobs (#7021): start the 0.9.11a1 dev server in four modes and run knobs_test.py against each.
#   plain          : no knobs
#   prod_react     : REFLEX_DEV_PROD_REACT=1
#   warmup         : REFLEX_VITE_WARMUP_ROUTES=1
#   both           : both
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
R=$SB/apps/hmr_runtime; S=$R/scripts; L=$R/logs; APP=$R/hmr_app
export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1
MODES=${MODES:-plain prod_react warmup both}
for mode in $MODES; do
  case $mode in
    plain) ENVS="" ;;
    prod_react) ENVS="REFLEX_DEV_PROD_REACT=1" ;;
    warmup) ENVS="REFLEX_VITE_WARMUP_ROUTES=1" ;;
    both) ENVS="REFLEX_DEV_PROD_REACT=1 REFLEX_VITE_WARMUP_ROUTES=1" ;;
  esac
  echo "=== MODE $mode ($ENVS)"
  cp $S/hmr_app_pristine.py $APP/hmr_app/hmr_app.py
  rm -rf $APP/.states $APP/hmr_app/__pycache__
  env -u NO_PROXY -u no_proxy $S/start_server.sh $SB/envs/smoke $APP 3103 8103 $L/dev_knobs_$mode.log $L/dev_knobs_$mode.pid $ENVS || { echo "START-FAILED $mode"; tail -40 $L/dev_knobs_$mode.log; continue; }
  sleep 3
  cp $APP/.web/vite.config.js $L/knobs_${mode}_vite.config.js
  $SB/envs/driver/bin/python $S/knobs_test.py --url http://localhost:3103 --backend-port 8103 --mode $mode --out $L/knobs_$mode --app-file $APP/hmr_app/hmr_app.py --edit > $L/knobs_${mode}_stdout.log 2>&1
  echo "knobs_test exit $?"
  if [ "$mode" = plain ]; then
    $SB/envs/driver/bin/python $S/safari_test.py --url http://localhost:3103 --out $L/safari_new_headmeta > $L/safari_new_headmeta_stdout.log 2>&1; echo "safari (plain, head meta) exit $?"
  fi
  $S/stop_server.sh $L/dev_knobs_$mode.pid 3103 8103
done
cp $S/hmr_app_pristine.py $APP/hmr_app/hmr_app.py
echo PIPELINE-DONE
