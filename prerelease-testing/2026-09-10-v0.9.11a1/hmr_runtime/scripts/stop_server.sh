#!/usr/bin/env bash
# Stop a server started by start_server.sh (TERM the process group, then KILL leftovers).
# usage: stop_server.sh <pid_file> <frontend_port> <backend_port>
set -u
PIDF=$1; FP=$2; BP=$3
if [ -f "$PIDF" ]; then
  PID=$(cat "$PIDF")
  PGID=$(ps -o pgid= -p "$PID" 2>/dev/null | tr -d ' ')
  kill -TERM "$PID" 2>/dev/null
  for i in $(seq 1 20); do kill -0 "$PID" 2>/dev/null || break; sleep 1; done
  [ -n "${PGID:-}" ] && kill -KILL -- "-$PGID" 2>/dev/null
fi
# anything still bound to our ports (bun/vite/granian) -- match by port in the command line only
for p in $(ps -eo pid,args | grep -E "[r]eflex run|[b]un run dev|[r]eact-router dev" | grep -E -- "--frontend-port $FP|--backend-port $BP" | awk '{print $1}'); do kill -KILL "$p" 2>/dev/null; done
sleep 1
for port in "$FP" "$BP"; do
  fuser -k -KILL "$port/tcp" 2>/dev/null && echo "killed listener(s) on port $port"
done
sleep 1
echo "remaining on ports $FP/$BP:"; (fuser "$FP/tcp" "$BP/tcp" 2>&1 | grep -E "[0-9]") || echo "  none"
