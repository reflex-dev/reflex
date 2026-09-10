#!/bin/bash
# Usage: stop_server.sh <app> <logname>   -- kills the whole process group started by run_server.sh,
# then any leftover process whose cwd is inside the app dir (bun/node/granian children).
set -u
SB=${SB:-/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad}
C=$SB/apps/up_counter_todo_clock
APP=$1; LOG=$2
PIDFILE=$C/logs/server/${APP}_$LOG.pid
if [ -f "$PIDFILE" ]; then
  PID=$(cat $PIDFILE)
  PGID=$(ps -o pgid= -p $PID 2>/dev/null | tr -d ' ')
  if [ -n "$PGID" ]; then
    kill -TERM -$PGID 2>/dev/null; sleep 3
    kill -KILL -$PGID 2>/dev/null
    echo "killed pgid $PGID"
  else
    echo "pid $PID already gone"
  fi
fi
for p in /proc/[0-9]*; do
  pid=${p#/proc/}; [ "$pid" = "$$" ] && continue
  cwd=$(readlink $p/cwd 2>/dev/null) || continue
  case "$cwd" in "$C/$APP"*) echo "killing leftover $pid ($(tr '\0' ' ' < $p/cmdline | cut -c1-80)) cwd=$cwd"; kill -KILL $pid 2>/dev/null;; esac
done
sleep 1
ps -eo pid,cmd | grep -E "reflex run|bun run|vite|granian|react-router" | grep -v grep | grep -E "$APP|rxdir_$APP" || echo "no $APP processes left"
exit 0
