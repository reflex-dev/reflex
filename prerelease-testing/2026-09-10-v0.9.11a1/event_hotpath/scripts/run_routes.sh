#!/bin/bash
# run_routes.sh <venv> <appdir> <fp> <bp> <label> <frontend_path or ''> [--env prod]
# Starts the routes app (dev, or prod with --env prod on ONE port), runs pw_routes.py, stops the server.
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
A=$SB/apps/event_hotpath
venv=$1; appdir=$2; fp=$3; bp=$4; label=$5; fpath=$6; shift 6
export HP_FRONTEND_PATH="$fpath"
$A/scripts/start_server.sh $venv $appdir $fp $bp routes_$label "$@"
sleep 30
$A/scripts/wait_up.sh "http://localhost:$fp$fpath/" 420 || { tail -30 $A/logs2/routes_$label.log; }
grep -n -E 'Compiling|Reflex 0' $A/logs2/routes_$label.log | head -2
cd $A/scripts && NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 timeout 700 $SB/envs/driver/bin/python pw_routes.py \
  --url http://localhost:$fp --frontend-path "$fpath" --out $A/logs2/pw_routes_$label --label $label 2>&1 \
  | grep -E '^\[|SUMMARY|WS pathnames|console_err_warn|page_errors|failed_requests|http_4xx|dialogs' | cut -c1-330
$A/scripts/stop_server.sh routes_$label
