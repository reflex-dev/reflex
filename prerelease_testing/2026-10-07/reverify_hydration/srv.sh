#!/bin/bash
# Compat wrapper for the 10-06 drivers (reconnect_driver.py, redis_restart_loop.py, token_leak_check.py):
#   srv.sh start <name> <venv> <dev|prod> <FP> <BP> [ENV=VAL...]  -> scripts/srv.sh with the hydapp source
#   srv.sh stop <name>
W=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/apps/reverify_hydration
if [ "$1" = start ]; then
  name=$2; venv=$3; mode=$4; FP=$5; BP=$6; shift 6
  exec $W/scripts/srv.sh start $name $venv $mode $W/src/hydapp $FP $BP "$@"
else
  exec $W/scripts/srv.sh "$@"
fi
