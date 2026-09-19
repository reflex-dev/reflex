#!/bin/bash
# usage: run_app.sh <appdir> <appname> <tag> [dev|prod]
set -u
SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad
BASE=$SB/apps/up_examples_a
APPDIR=$1; APP=$2; TAG=$3; MODE=${4:-dev}
VENV=${VENV:-$SB/envs/up_a}
LOG=$BASE/logs/$APP-$TAG.server.log
if [ "$MODE" = "prod" ]; then FP=3461; BP=3461; ARGS="--env prod --frontend-port $FP --backend-port $FP"; else FP=3460; BP=8460; ARGS="--frontend-port $FP --backend-port $BP"; fi

freeports() {
  for i in $(seq 1 20); do
    out=$(python3 $SB/bin/ports.py $FP $BP 2>/dev/null)
    [ -z "$out" ] && return 0
    for p in $(echo "$out" | grep -oE 'pids=[0-9,]+' | cut -d= -f2 | tr ',' ' '); do kill -9 $p 2>/dev/null; done
    sleep 1
  done
  echo "PORTS STILL BUSY: $(python3 $SB/bin/ports.py $FP $BP)"
  return 1
}

freeports || exit 4
export REFLEX_TELEMETRY_ENABLED=false
cd "$APPDIR" || exit 2
rm -f "$LOG"
nohup $VENV/bin/reflex run $ARGS --loglevel debug > "$LOG" 2>&1 &
SPID=$!
echo "server pid $SPID log $LOG venv $VENV"
code=""
for i in $(seq 1 200); do
  code=$(NO_PROXY=localhost,127.0.0.1 curl --noproxy '*' -s -o /dev/null -w '%{http_code}' http://localhost:$FP/ 2>/dev/null)
  if [ "$code" = "200" ]; then echo "UP after $((i*2))s"; break; fi
  sleep 2
done
if [ "$code" != "200" ]; then echo "FRONTEND NEVER CAME UP (last=$code)"; tail -40 "$LOG"; kill -9 $SPID 2>/dev/null; freeports; exit 3; fi
sleep 3
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python $BASE/scripts/drive.py "$APP" "http://localhost:$FP/" "$TAG" "$BASE/shots" > "$BASE/logs/$APP-$TAG.drive.json" 2>&1
DRC=$?
echo "drive exit $DRC"
kill $SPID 2>/dev/null; sleep 2; kill -9 $SPID 2>/dev/null
freeports
exit $DRC
