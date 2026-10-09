#!/bin/bash
# Usage: srv.sh start <name> <venv> <dev|prod> <app_src_dir> <FP> <BP> [ENV=VAL...]
#        srv.sh stop <name>
#        srv.sh sync <name> <app_src_dir>   (re-copy sources into $W/run/<name>, keeps .web)
# Copies the app's rxconfig.py + package .py files + assets into $W/run/<name> (keeps .web between starts) and runs
# $SB/envs/<venv>/bin/reflex run from there (a neutral dir, never a checkout) in its own process group.
# Sets RVH_VENV / VERIFY_VENV / VH_VENV=<venv>: every app asserts reflex.__file__ is under /envs/<venv>/.
# Prints "log=<file>" (logs: $W/logs/<name>-<n>.log). Ports must lie in $PORT_RANGES.
set -u
. "$(dirname "$0")/env.sh"
cmd=$1; name=$2
RUN=$W/run/$name
copy_src() {
  local SRC=$1; local app; app=$(basename "$SRC")
  mkdir -p "$RUN/$app" "$RUN/assets"
  cp "$SRC/rxconfig.py" "$RUN/" && cp "$SRC/$app/"*.py "$RUN/$app/" && { [ -d "$SRC/assets" ] && cp -r "$SRC/assets/." "$RUN/assets/" || true; }
}
in_range() {
  local p=$1 r
  for r in $PORT_RANGES; do [ "$p" -ge "${r%-*}" ] && [ "$p" -le "${r#*-}" ] && return 0; done
  return 1
}
case $cmd in
  sync) copy_src "$3"; echo "synced $RUN";;
  start)
    venv=$3; mode=$4; SRC=$5; FP=$6; BP=$7; shift 7
    for p in $FP $BP; do in_range "$p" || { echo "PORT $p OUT OF RANGE ($PORT_RANGES)"; exit 3; }; done
    # a leftover server on the port would silently take the drivers' traffic
    for p in $FP $BP; do lsof -iTCP:"$p" -sTCP:LISTEN -P -n > /dev/null 2>&1 && { echo "PORT $p ALREADY IN USE"; exit 5; }; done
    [ -x "$SB/envs/$venv/bin/reflex" ] || { echo "no reflex in $SB/envs/$venv"; exit 4; }
    copy_src "$SRC"
    n=$(ls "$W/logs/$name"-*.log 2>/dev/null | wc -l); n=$((n+1)); LOG=$W/logs/$name-$n.log
    if [ "$mode" = prod ]; then API=http://localhost:$FP; else API=http://localhost:$BP; fi
    cd "$RUN" || exit 1
    setsid env REFLEX_TELEMETRY_ENABLED=false REFLEX_API_URL="$API" RVH_VENV="$venv" VERIFY_VENV="$venv" VH_VENV="$venv" "$@" \
      "$SB/envs/$venv/bin/reflex" run --env "$mode" --frontend-port "$FP" --backend-port "$BP" --loglevel debug > "$LOG" 2>&1 < /dev/null &
    echo $! > "$W/run/$name.pid"
    echo "started $name pid=$(cat "$W/run/$name.pid") venv=$venv mode=$mode env=[$*] log=$LOG";;
  stop)
    pid=$(cat "$W/run/$name.pid" 2>/dev/null)
    if [ -n "$pid" ]; then
      kill -TERM -- -"$pid" 2>/dev/null
      for _ in $(seq 1 40); do ps -o pid= -g "$pid" >/dev/null 2>&1 || break; sleep 0.5; done
      if ps -o pid= -g "$pid" >/dev/null 2>&1; then kill -KILL -- -"$pid" 2>/dev/null; echo "SIGKILLed group $pid"; fi
      rm -f "$W/run/$name.pid"
      echo "stopped $name (pgid $pid)"
    fi;;
esac
