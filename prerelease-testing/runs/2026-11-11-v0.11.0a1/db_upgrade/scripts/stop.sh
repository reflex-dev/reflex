#!/usr/bin/env bash
# stop.sh <appdir> <ports...>: SIGTERM the process group, then KILL; report leftovers
set -u; . "$(dirname "$0")/env.sh"
A=$1; shift; PF=$W/logs/$(basename "$A").pid; PID=$(cat "$PF" 2>/dev/null)
if [ -n "$PID" ]; then kill -TERM -- -$PID 2>/dev/null; for i in $(seq 1 20); do kill -0 $PID 2>/dev/null || break; sleep 0.5; done; kill -KILL -- -$PID 2>/dev/null; fi
sleep 1
for p in "$@"; do for lp in $(lsof -nP -iTCP:$p -sTCP:LISTEN -t 2>/dev/null | sort -u); do echo "LEFTOVER port $p pid $lp -> kill"; kill -9 $lp; done; done
rm -f "$PF"; echo "stopped $PID"
