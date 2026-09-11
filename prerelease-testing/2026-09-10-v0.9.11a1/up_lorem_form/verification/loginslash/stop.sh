#!/bin/bash
set -u
APP=$1; shift
if [ -f "$APP/logs/server.pid" ]; then
  PID=$(cat "$APP/logs/server.pid"); kill -TERM -- "-$PID" 2>/dev/null; sleep 3; kill -KILL -- "-$PID" 2>/dev/null; rm -f "$APP/logs/server.pid"
fi
sleep 1
for port in "$@"; do
  pids=$(ss -ltnp 2>/dev/null | grep ":$port " | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u)
  [ -n "$pids" ] && { echo "port $port held by $pids, killing"; kill -KILL $pids 2>/dev/null; }
done
sleep 1
ss -ltnp 2>/dev/null | grep -E ":($(echo "$@" | tr ' ' '|')) " && echo "WARNING ports still bound" || echo "ports free: $*"
