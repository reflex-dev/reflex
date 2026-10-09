#!/bin/bash
# Usage: stop_app.sh <pidfile> -- TERM then KILL the whole process group
PID=$(cat "$1")
kill -TERM -- -$PID 2>/dev/null
for i in $(seq 1 20); do
  if ! kill -0 -- -$PID 2>/dev/null; then echo "stopped $PID"; rm -f "$1"; exit 0; fi
  sleep 0.5
done
kill -KILL -- -$PID 2>/dev/null; echo "killed $PID"; rm -f "$1"
