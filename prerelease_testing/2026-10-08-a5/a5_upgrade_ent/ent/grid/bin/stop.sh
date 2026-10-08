#!/usr/bin/env bash
# Kills the process group recorded by start.sh and verifies the reserved ports (3300-3319, 8300-8319) are free.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/a5_upgrade_ent/ent/grid
if [ -s $W/pids/current.pgid ]; then
  PGID=$(cat $W/pids/current.pgid)
  kill -TERM -- -$PGID 2>/dev/null
  for i in $(seq 1 20); do pgrep -g $PGID >/dev/null || break; sleep 1; done
  pgrep -g $PGID >/dev/null && { echo "SIGKILL pgid $PGID"; kill -KILL -- -$PGID 2>/dev/null; sleep 1; }
  : > $W/pids/current.pgid
fi
busy=0
for p in $(seq 3470 3479) $(seq 8470 8479); do
  if lsof -iTCP:$p -sTCP:LISTEN -nP >/dev/null 2>&1; then echo "still listening: $p"; lsof -iTCP:$p -sTCP:LISTEN -nP; busy=1; fi
done
[ $busy = 0 ] && echo "reserved ports free"
