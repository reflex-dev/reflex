#!/usr/bin/env bash
# Repro: `reflex run` under npm does not stop on SIGTERM without a TTY (orphaned node keeps the port,
# CLI blocks on the frontend stdout pipe). Compare with bun.
# Usage: npm_sigterm_repro.sh <venv_dir> <app_dir> <frontend_port> <backend_port> <use_npm 1|0> <log>
set -u
VENV=$1; APP=$2; FP=$3; BP=$4; USE_NPM=$5; LOG=$6
rm -rf "$APP"; mkdir -p "$APP"; cd "$APP" || exit 2
{
echo "### reflex $("$VENV/bin/reflex" --version 2>/dev/null) REFLEX_USE_NPM=$USE_NPM app=$APP"
REFLEX_TELEMETRY_ENABLED=false "$VENV/bin/reflex" init --template blank >/dev/null 2>&1 || echo "init failed"
REFLEX_USE_NPM=$USE_NPM REFLEX_TELEMETRY_ENABLED=false setsid "$VENV/bin/reflex" run --frontend-port "$FP" --backend-port "$BP" > "$LOG.server" 2>&1 &
PID=$!
for i in $(seq 1 120); do [ "$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:$FP/)" = 200 ] && break; sleep 2; done
echo "frontend up; reflex CLI pid=$PID; process group before SIGTERM:"
ps -eo pid,ppid,pgid,stat,cmd | awk -v p=$PID '$3==p' | cut -c1-140
echo "--- kill -TERM $PID (single process, no TTY)"
kill -TERM "$PID"
for i in $(seq 1 15); do kill -0 "$PID" 2>/dev/null || break; sleep 2; done
if kill -0 "$PID" 2>/dev/null; then echo "RESULT: reflex CLI STILL RUNNING 30s after SIGTERM"; else echo "RESULT: reflex CLI exited"; fi
echo "listeners on $FP/$BP after 30s:"; lsof -iTCP -sTCP:LISTEN -P -n 2>/dev/null | grep -E ":($FP|$BP)\b" || echo "  (none)"
echo "process group after 30s:"; ps -eo pid,ppid,pgid,stat,cmd | awk -v p=$PID '$3==p' | cut -c1-140
for t in /proc/$PID/task/*; do [ -e "$t" ] && echo "  thread $(basename $t) wchan=$(cat $t/wchan 2>/dev/null)"; done
echo "--- cleanup: SIGKILL process group $PID"
kill -KILL -- -"$PID" 2>/dev/null; sleep 1
lsof -iTCP -sTCP:LISTEN -P -n 2>/dev/null | grep -E ":($FP|$BP)\b" || echo "  ports free"
echo "server log tail:"; tail -5 "$LOG.server" | sed 's/^/  | /'
} > "$LOG" 2>&1
cat "$LOG"
