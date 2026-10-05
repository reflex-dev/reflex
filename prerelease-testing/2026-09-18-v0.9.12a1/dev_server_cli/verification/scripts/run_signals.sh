#!/bin/bash
SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad
W=$SB/apps/verify_dev_server_cli
export REFLEX_TELEMETRY_ENABLED=false
export PORTS_PY=$SB/bin/ports.py
cd $W
set -x
python3 $W/scripts/signal_test.py $SB/envs/shared $W/dsc      V_N_proc  TERM proc  $W/logs 3884 8884
python3 $W/scripts/signal_test.py $SB/envs/shared $W/dsc      V_N_group TERM group $W/logs 3885 8885
python3 $W/scripts/signal_test.py $SB/envs/prev   $W/dsc_prev V_P_proc  TERM proc  $W/logs 3886 8886
python3 $W/scripts/signal_test.py $SB/envs/prev   $W/dsc_prev V_P_group TERM group $W/logs 3887 8887
echo ALLDONE
