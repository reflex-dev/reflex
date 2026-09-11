#!/bin/bash
# Adjacent probe: does `reflex run` (dev) exit on SIGTERM / SIGINT, and does it
# leave its frontend child behind?
#
# Usage: shutdown_probe.sh <reflex-bin> <app-dir> <frontend-port> <backend-port> <label> <logdir> <SIGNAL>
set -u
REFLEX="$1"; APP="$2"; FP="$3"; BP="$4"; LABEL="$5"; LOGDIR="$6"; SIG="${7:-TERM}"
cd "$APP" || exit 1
nohup env REFLEX_TELEMETRY_ENABLED=false "$REFLEX" run --frontend-port "$FP" --backend-port "$BP" --loglevel info \
  > "$LOGDIR/shutdown_${LABEL}.log" 2>&1 &
PARENT=$!
for i in $(seq 1 40); do
  code=$(curl -s -o /dev/null -w '%{http_code}' --noproxy '*' --max-time 5 "http://localhost:$FP/" 2>/dev/null)
  [ "$code" = "200" ] && break
  sleep 3
done
echo "[$LABEL/$SIG] parent=$PARENT frontend_http=$code ready_after=$((i*3))s"
KIDS=$(pgrep -P "$PARENT" | tr '\n' ' ')
echo "[$LABEL/$SIG] direct children before signal: $KIDS"
T0=$(date +%s)
kill -"$SIG" "$PARENT"
STATE=""; ELAPSED=""
for i in $(seq 1 40); do
  STATE=$(ps -p "$PARENT" -o stat= --no-headers 2>/dev/null | tr -d ' ')
  if [ -z "$STATE" ] || [ "${STATE:0:1}" = "Z" ]; then ELAPSED=$(( $(date +%s) - T0 )); break; fi
  sleep 1
done
echo "[$LABEL/$SIG] parent stopped after ${ELAPSED:->40}s (final state='${STATE:-gone}')"
sleep 2
STILL=$(ps -eo pid,args --no-headers | grep "$APP/.web" | grep -v grep | awk '{print $1}' | tr '\n' ' ')
echo "[$LABEL/$SIG] frontend/child pids alive after: ${STILL:-none}"
AFTER=$(curl -s -o /dev/null -w '%{http_code}' --noproxy '*' --max-time 5 "http://localhost:$FP/" 2>/dev/null)
echo "[$LABEL/$SIG] frontend still answering: $AFTER"
for p in $STILL; do kill -9 "$p" 2>/dev/null; done
kill -9 "$PARENT" 2>/dev/null
sleep 1
echo "[$LABEL/$SIG] cleanup remaining: $(ps -eo pid,args --no-headers | grep "$APP/.web" | grep -v grep | wc -l)"
