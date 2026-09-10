#!/bin/bash
# start_server.sh <venv> <appdir> <fp> <bp> <logname> [extra reflex run args...]
# Starts `reflex run` detached (setsid) with REFLEX_TELEMETRY_ENABLED=false, writes logs/<logname>.log and logs/<logname>.pid.
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
A=$SB/apps/event_hotpath
venv=$1; appdir=$2; fp=$3; bp=$4; name=$5; shift 5
cd $A/$appdir || exit 1
export REFLEX_TELEMETRY_ENABLED=false
setsid nohup $SB/envs/$venv/bin/reflex run --frontend-port $fp --backend-port $bp --loglevel debug "$@" > $A/logs2/$name.log 2>&1 &
echo $! > $A/logs2/$name.pid
echo "started $venv $appdir fp=$fp bp=$bp pid=$(cat $A/logs2/$name.pid) log=$A/logs2/$name.log"
