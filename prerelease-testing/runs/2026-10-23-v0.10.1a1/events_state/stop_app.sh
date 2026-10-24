#!/bin/bash
# Usage: stop_app.sh <tag> -- TERM then KILL the process group recorded in $W/pids/<tag>.pid
: "${SB:?}"; W=${W:-$SB/apps/events_state}
F=$W/pids/$1.pid; [ -f "$F" ] || { echo "no pidfile $F"; exit 0; }
PID=$(cat "$F")
kill -TERM -- -$PID 2>/dev/null
for i in $(seq 1 30); do
  if ! kill -0 -- -$PID 2>/dev/null; then echo "stopped $PID"; rm -f "$F"; exit 0; fi
  sleep 0.5
done
kill -KILL -- -$PID 2>/dev/null; echo "killed $PID"; rm -f "$F"
