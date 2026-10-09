#!/bin/bash
# Compat wrapper for drivers/reconnect_driver.py, redis_restart_loop.py, token_leak_check.py (they call it):
#   srv_hydapp.sh start <name> <venv> <dev|prod> <FP> <BP> [ENV=VAL...]  -> srv.sh with src/hydapp
#   srv_hydapp.sh stop <name>
S=$(cd "$(dirname "$0")" && pwd)
if [ "$1" = start ]; then
  name=$2; venv=$3; mode=$4; FP=$5; BP=$6; shift 6
  exec "$S/srv.sh" start "$name" "$venv" "$mode" "$S/../src/hydapp" "$FP" "$BP" "$@"
else
  exec "$S/srv.sh" "$@"
fi
