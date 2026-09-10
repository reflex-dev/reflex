#!/bin/bash
# stop_server.sh <logname>  -- kills the process group started by start_server.sh
A=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad/apps/event_hotpath
LOGDIR=${LOGDIR:-logs3}
pid=$(cat $A/$LOGDIR/$1.pid 2>/dev/null) || { echo "no pid for $1"; exit 0; }
pgid=$(ps -o pgid= -p $pid 2>/dev/null | tr -d ' ')
[ -n "$pgid" ] && kill -TERM -- -$pgid 2>/dev/null
sleep 3
[ -n "$pgid" ] && kill -KILL -- -$pgid 2>/dev/null
echo "stopped $1 (pid $pid pgid $pgid)"
