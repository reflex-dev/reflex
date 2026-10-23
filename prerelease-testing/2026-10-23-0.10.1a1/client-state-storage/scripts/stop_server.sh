#!/bin/bash
# Usage: stop_server.sh <logname>  -- kills the reflex run process tree started by run_server.sh
A=/tmp/claude-0/-home-user-reflex/7eb9e30f-e96c-5de5-9b0e-4a12be91e0f3/scratchpad/prt/apps/client-state-storage
PID=$(cat $A/logs/$1.pid)
pkill -TERM -P $PID 2>/dev/null; kill -TERM $PID 2>/dev/null
for i in 1 2 3 4 5 6 7 8 9 10; do kill -0 $PID 2>/dev/null || break; sleep 1; done
kill -0 $PID 2>/dev/null && kill -KILL $PID
# leftovers bound to our ports
for p in $(lsof -t -iTCP:3140-3159 -sTCP:LISTEN 2>/dev/null; lsof -t -iTCP:8140-8159 -sTCP:LISTEN 2>/dev/null); do kill -KILL $p 2>/dev/null; done
sleep 1; lsof -iTCP:3140-3159 -sTCP:LISTEN 2>/dev/null; lsof -iTCP:8140-8159 -sTCP:LISTEN 2>/dev/null || echo "ports free"
