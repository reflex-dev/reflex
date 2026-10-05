#!/bin/bash
# usage: _run.sh <appdir> <logname> <fport> <bport> [extra reflex args...]
set -u
SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad
APP=$1; LOG=$2; FP=$3; BP=$4; shift 4
cd $SB/apps/up_examples_c/$APP || exit 1
export REFLEX_TELEMETRY_ENABLED=false
nohup $SB/envs/upc/bin/reflex run --frontend-port $FP --backend-port $BP "$@" > $SB/apps/up_examples_c/_logs/$LOG.log 2>&1 &
echo "PID=$!"
