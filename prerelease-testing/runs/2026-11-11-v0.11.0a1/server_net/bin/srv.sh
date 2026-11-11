#!/usr/bin/env bash
# Start/stop a probe app of the server_net cluster in its own process group.
#   srv.sh start <label> <venv> <app> <reflex run args...>   (extra env: export before calling)
#   srv.sh stop <label>
#   srv.sh wait <url> [secs] [text]
# The app source $W/src/<app> is synced into $W/run/<venv>/<app> (keeps .web between runs).
set -u
SB=${SB:?set SB}
W=${W:-$SB/apps/server_net}
cmd=$1; shift
case $cmd in
start)
  label=$1 venv=$2 app=$3; shift 3
  dir=$W/run/$venv/$app
  mkdir -p "$dir" "$W/logs"
  tar -C "$W/src/$app" --exclude .web --exclude __pycache__ -cf - . | tar -C "$dir" -xf -
  for p in "$@"; do :; done
  log=$W/logs/$label.log
  : > "$log"
  rm -f "$W/logs/$label.pid"
  ( cd "$dir" && NA_VENV=$venv REFLEX_TELEMETRY_ENABLED=false PIDF="$W/logs/$label.pid" setsid bash -c 'echo $$ > "$PIDF"; exec "$0" run "$@"' "$SB/envs/$venv/bin/reflex" "$@" >"$log" 2>&1 < /dev/null & )
  for i in $(seq 1 20); do [ -s "$W/logs/$label.pid" ] && break; sleep 0.1; done
  echo "started $label pid=$(cat $W/logs/$label.pid) log=$log"
  ;;
stop)
  label=$1
  pid=$(cat "$W/logs/$label.pid" 2>/dev/null) || { echo "no pid for $label"; exit 0; }
  kill -INT -- -"$pid" 2>/dev/null
  for i in $(seq 1 30); do kill -0 -- -"$pid" 2>/dev/null || break; sleep 0.5; done
  kill -9 -- -"$pid" 2>/dev/null && echo "killed -9 $label"
  rm -f "$W/logs/$label.pid"
  echo "stopped $label"
  ;;
wait)
  url=$1 secs=${2:-360} text=${3:-}
  for i in $(seq 1 "$secs"); do
    out=$(curl --noproxy '*' -s -m 5 "$url" 2>/dev/null) && { [ -z "$text" ] || grep -q -- "$text" <<<"$out"; } && { echo "up after ${i}s: $url"; exit 0; }
    if [ -n "${LABEL:-}" ] && ! kill -0 "$(cat $W/logs/$LABEL.pid 2>/dev/null)" 2>/dev/null; then echo "server $LABEL exited"; tail -20 $W/logs/$LABEL.log; exit 2; fi
    sleep 1
  done
  echo "TIMEOUT waiting for $url"; exit 1
  ;;
esac
