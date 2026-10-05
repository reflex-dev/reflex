#!/bin/bash
# usage: signal_test.sh <venv> <appdir> <label> <SIG> <proc|group> <logdir> <fp> <bp> [extra reflex args...]
VENV=$1; APPDIR=$2; LABEL=$3; SIG=$4; TARGET=$5; LOGDIR=$6; FP=$7; BP=$8; shift 8
LOG=$LOGDIR/sig_${LABEL}.log
cd "$APPDIR" || exit 9
REFLEX_TELEMETRY_ENABLED=false setsid "$VENV/bin/reflex" run --frontend-port "$FP" --backend-port "$BP" "$@" > "$LOG" 2>&1 &
PID=$!
READY=0
for i in $(seq 1 180); do
  if grep -qE "Backend running at|App running at" "$LOG" 2>/dev/null; then READY=1; break; fi
  kill -0 $PID 2>/dev/null || { echo "DIED EARLY"; break; }
  sleep 1
done
echo "### label=$LABEL sig=$SIG target=$TARGET extra='$*' ready=$READY after=${i}s"
sleep 4
PGID=$(ps -o pgid= -p $PID 2>/dev/null | tr -d ' ')
echo "pgid=$PGID members_before: $(ps -eo pid,comm --no-headers | awk 'NR>0' >/dev/null; ps -eo pid,pgid,comm --no-headers | awk -v g=$PGID '$2==g{printf "%s(%s) ",$1,$3}')"
T0=$(date +%s.%N)
if [ "$TARGET" = "group" ]; then kill -$SIG -$PGID 2>/dev/null; else kill -$SIG $PID 2>/dev/null; fi
RC="TIMEOUT"
for j in $(seq 1 300); do   # 30s max, 0.1s steps
  if ! kill -0 $PID 2>/dev/null; then wait $PID; RC=$?; break; fi
  sleep 0.1
done
T1=$(date +%s.%N)
echo "EXIT_CODE=$RC elapsed=$(echo "$T1 - $T0" | bc)s"
sleep 2
SURV=$(ps -eo pid,pgid,comm --no-headers | awk -v g=$PGID '$2==g{printf "%s(%s) ",$1,$3}')
echo "survivors_in_pgid: ${SURV:-NONE}"
echo "ports_still_bound:"; python3 $SB_BIN/ports.py $FP $BP 2>/dev/null
echo "log_143_or_error_lines:"; grep -nE "exit code|143|Traceback|\[ERROR\]" "$LOG" | tail -10
echo "log_tail:"; tail -5 "$LOG"
# hard cleanup
[ -n "$PGID" ] && kill -9 -$PGID 2>/dev/null
sleep 2
echo "after_force_kill_ports:"; python3 $SB_BIN/ports.py $FP $BP 2>/dev/null
echo "###END"
