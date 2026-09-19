#!/bin/bash
# usage: lockswitch.sh <venv> <appdir> <label> <fp> <bp> <logdir> [USE_NPM]
VENV=$1; APPDIR=$2; LABEL=$3; FP=$4; BP=$5; LOGDIR=$6; USENPM=$7
LOG=$LOGDIR/lock_${LABEL}.log
cd "$APPDIR" || exit 9
echo "--- $LABEL: reflex.lock before: $(ls reflex.lock 2>/dev/null | tr '\n' ' ')"
if [ -n "$USENPM" ]; then export REFLEX_USE_NPM=1; fi
REFLEX_TELEMETRY_ENABLED=false setsid "$VENV/bin/reflex" run --frontend-port "$FP" --backend-port "$BP" > "$LOG" 2>&1 &
sleep 1
RPID=$(python3 "$PORTS_PY" "$BP" 2>/dev/null | grep -o 'pids=[0-9,]*' | cut -d= -f2 | cut -d, -f1)
OK=no
for i in $(seq 1 300); do
  C=$(curl -s --noproxy '*' -m 3 -o /dev/null -w '%{http_code}' "http://localhost:$FP/" 2>/dev/null)
  if [ "$C" = "200" ]; then OK="yes(${i}s)"; break; fi
  if grep -qE "lockfile had changes|frozen-lockfile|error:|Traceback" "$LOG" 2>/dev/null; then OK="ERROR(${i}s)"; break; fi
  sleep 1
done
echo "--- $LABEL: frontend200=$OK"
echo "--- $LABEL: reflex.lock after: $(ls reflex.lock 2>/dev/null | tr '\n' ' ')"
echo "--- $LABEL: error lines:"; grep -nE "lockfile had changes|frozen-lockfile|^error:|Traceback|npm error" "$LOG" | head -8
for p in $(python3 "$PORTS_PY" "$FP" "$BP" 2>/dev/null | grep -o 'pids=[0-9,]*' | cut -d= -f2 | tr ',' ' '); do kill -9 "$p" 2>/dev/null; done
sleep 3
echo "--- $LABEL: ports after kill:"; python3 "$PORTS_PY" "$FP" "$BP" 2>/dev/null
echo "###END_$LABEL"
