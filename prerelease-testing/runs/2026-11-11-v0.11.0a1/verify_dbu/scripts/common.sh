# source me: shared vars for verify_dbu
export SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad
export W=$SB/apps/verify_dbu
export REFLEX_TELEMETRY_ENABLED=false
EX=$SB/downloads/reflex-examples
# r <venv> <appdir> <args...>: run reflex from the venv inside appdir, print rc
r() { local V=$SB/envs/$1 A=$2; shift 2; (cd "$A" && "$V/bin/reflex" "$@"); echo "[rc=$?] ($1) reflex $*"; }
a() { local V=$SB/envs/$1 A=$2; shift 2; (cd "$A" && "$V/bin/alembic" "$@"); echo "[rc=$?] ($1) alembic $*"; }
s() { sha256sum "$@" | cut -c1-16; }
busy() { curl -s --noproxy '*' -o /dev/null --max-time 2 "http://localhost:$1/" ; }
# cpapp <src> <dst>: copy an app dir without build output
cpapp() { mkdir -p "$2"; (cd "$1" && tar --exclude=./.web --exclude=./.states --exclude=__pycache__ --exclude=./reflex.lock -cf - .) | (cd "$2" && tar xf -); }
# runapp <venv> <appdir> <fp> <bp> <log> <wait-seconds>: start reflex run in its own process group,
# wait for fe+be 200 or death; leaves the pgid in $W/logs/run.pid
runapp() {
  local V=$SB/envs/$1 A=$2 FP=$3 BP=$4 LOG=$5 T=${6:-400}
  busy $FP && { echo "PORT $FP BUSY"; return 2; }; busy $BP && { echo "PORT $BP BUSY"; return 2; }
  (cd "$A" && setsid "$V/bin/reflex" run --frontend-port $FP --backend-port $BP --loglevel debug > "$LOG" 2>&1 < /dev/null & echo $! > $W/logs/run.pid)
  local PID=$(cat $W/logs/run.pid) t0=$(date +%s)
  while :; do
    fc=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' --max-time 5 http://localhost:$FP/)
    bc=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' --max-time 5 http://localhost:$BP/ping)
    [ "$fc" = 200 ] && [ "$bc" = 200 ] && { echo "UP after $(( $(date +%s)-t0 ))s (pid $PID)"; return 0; }
    kill -0 $PID 2>/dev/null || { echo "SERVER EXITED after $(( $(date +%s)-t0 ))s fe=$fc be=$bc"; return 1; }
    [ $(( $(date +%s)-t0 )) -gt $T ] && { echo "TIMEOUT fe=$fc be=$bc (pid $PID alive)"; return 1; }
    sleep 3
  done
}
stopapp() {
  local PID=$(cat $W/logs/run.pid 2>/dev/null); [ -n "$PID" ] || return 0
  kill -TERM -- -$PID 2>/dev/null; for i in $(seq 1 20); do kill -0 -- -$PID 2>/dev/null || break; sleep 0.5; done
  kill -KILL -- -$PID 2>/dev/null; rm -f $W/logs/run.pid; sleep 1
  for p in "$@"; do lsof -nP -iTCP:$p -sTCP:LISTEN -t 2>/dev/null | while read lp; do echo "LEFTOVER $p pid $lp"; kill -9 $lp; done; done
  echo "stopped pgid $PID"
}
