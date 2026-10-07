#!/usr/bin/env bash
# Kill the process group recorded by start_server.sh and verify our ports are free.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
PF=$SB/apps/ent_grid/pids/current.pid
if [ -f "$PF" ]; then
  PID=$(cat "$PF")
  kill -TERM -- "-$PID" 2>/dev/null
  for i in $(seq 1 15); do kill -0 -- "-$PID" 2>/dev/null || break; sleep 1; done
  kill -KILL -- "-$PID" 2>/dev/null
  rm -f "$PF"
fi
sleep 1
if lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | grep -E ':(33[01][0-9]|83[01][0-9])\b'; then echo "WARNING: ports still bound"; else echo "ports 3300-3319/8300-8319 free"; fi
