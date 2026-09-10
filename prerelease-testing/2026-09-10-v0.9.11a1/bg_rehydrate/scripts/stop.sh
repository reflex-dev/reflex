#!/bin/bash
# Usage: stop.sh <label>  -- kills the process group of the server started by serve.sh
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
A=$SB/apps/bg_rehydrate
PIDF=$A/logs/$1.pid
[ -f "$PIDF" ] || { echo "no pid file"; exit 0; }
PID=$(cat "$PIDF")
pkill -TERM -P "$PID" 2>/dev/null; kill -TERM "$PID" 2>/dev/null
sleep 2
pkill -KILL -P "$PID" 2>/dev/null; kill -KILL "$PID" 2>/dev/null
# leftover children (granian workers / vite / bun) that reparented
for p in $(pgrep -f "bg_rehydrate/.*(reflex|granian|vite|bun)" ); do kill -KILL $p 2>/dev/null; done
rm -f "$PIDF"
ps aux | grep -E 'reflex run|granian|vite|bun' | grep -v grep | grep bg_rehydrate || echo "no bg_rehydrate server processes left"
