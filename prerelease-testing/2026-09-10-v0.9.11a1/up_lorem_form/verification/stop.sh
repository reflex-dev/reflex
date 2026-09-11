#!/bin/bash
# stop.sh <app_dir> <port>...
APP="$1"; shift
if [ -f "$APP/server.pid" ]; then
  PID=$(cat "$APP/server.pid"); PGID=$(ps -o pgid= -p "$PID" 2>/dev/null | tr -d ' ')
  [ -n "$PGID" ] && kill -TERM -"$PGID" 2>/dev/null
  sleep 3
  [ -n "$PGID" ] && kill -KILL -"$PGID" 2>/dev/null
  rm -f "$APP/server.pid"
fi
sleep 1
for p in "$@"; do
  if (exec 3<>/dev/tcp/127.0.0.1/$p) 2>/dev/null; then echo "PORT $p STILL OPEN"; else echo "port $p free"; fi
done
