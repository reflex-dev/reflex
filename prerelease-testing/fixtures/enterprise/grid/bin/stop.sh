#!/usr/bin/env bash
# Kills the process group recorded by start.sh and verifies the grid ports (3600-3619, 8600-8619) are free.
. "$(dirname "$0")/../../lib.sh"; W=$WORK/grid
if [ -s "$W/pids/current.pgid" ]; then
  PGID=$(cat "$W/pids/current.pgid")
  kill -TERM -- -$PGID 2>/dev/null
  for i in $(seq 1 20); do pgrep -g $PGID >/dev/null || break; sleep 1; done
  pgrep -g $PGID >/dev/null && { echo "SIGKILL pgid $PGID"; kill -KILL -- -$PGID 2>/dev/null; sleep 1; }
  : > "$W/pids/current.pgid"
fi
acct_stub_stop
busy=0
for p in $(seq 3600 3619) $(seq 8600 8619); do
  if lsof -iTCP:$p -sTCP:LISTEN -nP >/dev/null 2>&1; then echo "still listening: $p"; lsof -iTCP:$p -sTCP:LISTEN -nP; busy=1; fi
done
[ $busy = 0 ] && echo "reserved ports free"
