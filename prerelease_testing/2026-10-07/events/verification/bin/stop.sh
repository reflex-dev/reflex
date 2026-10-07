#!/usr/bin/env bash
# usage: stop.sh [label...]  -- kills the process group of each pid file given (default: all), then lists leftovers in my ranges
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/verify_events_0
if [ $# -gt 0 ]; then FILES=""; for l in "$@"; do FILES="$FILES $W/pids/$l.pid"; done; else FILES=$(ls $W/pids/*.pid 2>/dev/null); fi
for f in $FILES; do
  [ -f "$f" ] || continue
  pid=$(cat "$f")
  if kill -0 "$pid" 2>/dev/null; then
    kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null
    for i in 1 2 3 4 5 6 7 8 9 10; do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
    kill -KILL -- "-$pid" 2>/dev/null
  fi
  rm -f "$f"
  echo "stopped $(basename $f .pid) (pid $pid)"
done
sleep 1
echo "--- listeners in my ranges (3640-3659, 8640-8659):"
ss -ltnp 2>/dev/null | awk 'NR>1 {n=split($4,a,":"); p=a[n]; if ((p>=3640 && p<=3659) || (p>=8640 && p<=8659)) print}'
echo "--- end"
