#!/bin/bash
# Stop the server started by serve.sh: kill its whole process group (reflex + bun + node children),
# then verify nothing is left listening on the given ports.
# usage: stop.sh <app_dir> <port> [<port>...]
set -u
APP=$1; shift
if [ -f "$APP/logs/server.pid" ]; then
  PID=$(cat "$APP/logs/server.pid")
  kill -TERM -- "-$PID" 2>/dev/null
  sleep 3
  kill -KILL -- "-$PID" 2>/dev/null
  rm -f "$APP/logs/server.pid"
fi
sleep 1
for port in "$@"; do
  pids=$(ss -ltnp 2>/dev/null | grep ":$port " | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u)
  if [ -n "$pids" ]; then echo "port $port still held by $pids, killing"; kill -KILL $pids 2>/dev/null; fi
done
sleep 1
ss -ltnp 2>/dev/null | grep -E ":($(echo "$@" | tr ' ' '|')) " && echo "WARNING: ports still bound" || echo "ports free: $*"
ps aux | grep -E "reflex run|react-router dev|vite" | grep -v grep | grep -E "$(basename "$APP")" && echo "WARNING: leftover processes" || echo "no leftover processes for $(basename "$APP")"
