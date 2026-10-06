#!/bin/bash
# Usage: stop.sh <pidfile> -- kills the whole process group started by start.sh
PIDF=$1; PID=$(cat "$PIDF")
kill -TERM -- -$PID 2>/dev/null
for i in $(seq 1 30); do
  if ! kill -0 -- -$PID 2>/dev/null; then echo "stopped $PID"; rm -f "$PIDF"; exit 0; fi
  sleep 0.5
done
kill -KILL -- -$PID 2>/dev/null; echo "killed $PID"; rm -f "$PIDF"
