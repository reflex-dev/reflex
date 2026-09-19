#!/bin/bash
# usage: lock_probe.sh <venv> <appdir> <label> <fp> <bp> <logdir> [ENVASSIGN]
# Starts `reflex run --loglevel debug`, waits for the frontend to answer 200 (so the
# install really completed), records which package installer was chosen and what
# reflex.lock/ holds afterwards, then kills the whole process group.
VENV=$1; APPDIR=$2; LABEL=$3; FP=$4; BP=$5; LOGDIR=$6; ENVASSIGN=$7
LOG=$LOGDIR/lockv_${LABEL}.log
cd "$APPDIR" || exit 9
echo "### $LABEL  REFLEX_USE_NPM=${ENVASSIGN:-<unset>}"
echo "### reflex.lock BEFORE: $(ls reflex.lock 2>/dev/null | tr '\n' ' ')"
if [ -n "$ENVASSIGN" ]; then export REFLEX_USE_NPM="$ENVASSIGN"; else unset REFLEX_USE_NPM; fi
REFLEX_TELEMETRY_ENABLED=false setsid "$VENV/bin/reflex" run --loglevel debug \
    --frontend-port "$FP" --backend-port "$BP" > "$LOG" 2>&1 &
BGPID=$!
PGID=$(ps -o pgid= -p $BGPID | tr -d ' ')
OK=no
for i in $(seq 1 240); do
  C=$(curl -s --noproxy '*' -m 3 -o /dev/null -w '%{http_code}' "http://localhost:$FP/" 2>/dev/null)
  [ "$C" = "200" ] && { OK="yes(${i}s)"; break; }
  grep -qE "lockfile had changes|frozen-lockfile|^error:|Traceback" "$LOG" 2>/dev/null && { OK="ERROR(${i}s)"; break; }
  sleep 1
done
echo "### frontend200=$OK"
echo "### installer line: $(grep -o 'Using package installer at:.*' "$LOG" | head -1)"
echo "### install cmd:    $(grep -oE "Running command: \['[^']*(npm|bun)'[^]]*install[^]]*\]" "$LOG" | head -1)"
echo "### reflex.lock AFTER:  $(ls reflex.lock 2>/dev/null | tr '\n' ' ')"
echo "### .web locks AFTER:   $(ls .web/bun.lock .web/package-lock.json 2>/dev/null | tr '\n' ' ')"
kill -9 -"$PGID" 2>/dev/null
sleep 3
echo "### ports after kill:"; python3 "$SB_PORTS" "$FP" "$BP" 2>/dev/null
echo "###END_$LABEL"
