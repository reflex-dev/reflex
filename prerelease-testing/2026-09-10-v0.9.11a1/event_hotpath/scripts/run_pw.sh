#!/bin/bash
# run_pw.sh <venv> <appdir> <fp> <bp> <label> [pw_hotpath.py args...]
# Starts the hotpath app dev server (frontend+backend), waits for the frontend, runs pw_hotpath.py, stops the server.
# Env passthrough: HP_TASK_FACTORY=1 / HP_GWT=1 reach the app (read at import time).
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
A=$SB/apps/event_hotpath
LOGDIR=${LOGDIR:-logs3}
venv=$1; appdir=$2; fp=$3; bp=$4; label=$5; shift 5
$A/scripts/start_server.sh $venv $appdir $fp $bp hotpath_$label
sleep 20
$A/scripts/wait_up.sh "http://localhost:$fp/" 420 || { tail -30 $A/$LOGDIR/hotpath_$label.log; }
sleep 3
cd $A/scripts && NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 timeout 900 $SB/envs/driver/bin/python pw_hotpath.py \
  --url http://localhost:$fp --out $A/$LOGDIR/pw_hotpath_$label --label $label "$@" 2>&1 \
  | grep -E '^\[|SUMMARY|console_err_warn|page_errors|failed_requests|http_4xx|dialogs' | cut -c1-400
$A/scripts/stop_server.sh hotpath_$label
echo "--- server log scan ($LOGDIR/hotpath_$label.log):"
grep -n -i -E 'traceback|warn|destroyed|eager|never awaited|Unexpected exit' $A/$LOGDIR/hotpath_$label.log | grep -v -i -E 'sitemap|redis_lock_warning|peer dependency|Radix Themes|RouterData.page' | head -12
