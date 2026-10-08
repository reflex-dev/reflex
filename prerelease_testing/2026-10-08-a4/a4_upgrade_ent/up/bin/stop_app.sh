#!/usr/bin/env bash
# Usage: stop_app.sh <appdir> <port>...
# 1) SIGTERM only the main `reflex run` pid (no TTY) and time its exit,
# 2) report anything still listening on the given ports (orphans),
# 3) then hard-kill the process group and any remaining listeners on those ports.
set -u
APPDIR=$1; shift
PORTS="$*"
PID=$(cat "$(dirname "$0")/../run/$(basename "$APPDIR").pid" 2>/dev/null)
if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
  kill -TERM "$PID"
  for i in $(seq 1 30); do kill -0 "$PID" 2>/dev/null || break; sleep 0.5; done
  if kill -0 "$PID" 2>/dev/null; then echo "SHUTDOWN: main pid $PID still alive 15s after SIGTERM"; else echo "SHUTDOWN: main pid $PID exited after SIGTERM in ~$(( i / 2 ))s"; fi
else
  echo "SHUTDOWN: no live main pid ($PID)"
fi
sleep 1
left=""
for p in $PORTS; do
  for lp in $(lsof -nP -iTCP:$p -sTCP:LISTEN -t 2>/dev/null | sort -u); do
    left="$left $lp"
    echo "ORPHAN after SIGTERM: port=$p pid=$lp cmd=$(tr '\0' ' ' < /proc/$lp/cmdline | cut -c1-140)"
  done
done
[ -z "$left" ] && echo "SHUTDOWN: all ports free after SIGTERM of main pid"
[ -n "$PID" ] && kill -KILL -- "-$PID" 2>/dev/null
for lp in $left; do kill -KILL "$lp" 2>/dev/null; done
sleep 1
for p in $PORTS; do
  for lp in $(lsof -nP -iTCP:$p -sTCP:LISTEN -t 2>/dev/null | sort -u); do echo "STILL LISTENING port=$p pid=$lp -> kill -9"; kill -KILL "$lp"; done
done
rm -f "$(dirname "$0")/../run/$(basename "$APPDIR").pid"
exit 0
