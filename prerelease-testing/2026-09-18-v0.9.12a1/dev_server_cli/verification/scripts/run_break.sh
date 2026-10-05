#!/bin/bash
SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad
W=$SB/apps/verify_dev_server_cli
export REFLEX_TELEMETRY_ENABLED=false
cd $W
python3 $W/scripts/break_reload_probe.py $SB/envs/shared $W/dsc      3888 8888 new  $W/logs
python3 $W/scripts/break_reload_probe.py $SB/envs/prev   $W/dsc_prev 3889 8889 prev $W/logs
echo BREAKDONE
