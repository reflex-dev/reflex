#!/usr/bin/env bash
# serve.sh start <venv> <appdir> <label> <mode: dev|prod|prod-be|dev-be> <port(s)> [extra reflex args...]
#   dev:     --frontend-port FP --backend-port BP   (port arg "FP:BP")
#   prod:    --env prod --frontend-port P --backend-port P (port arg "P"); REFLEX_API_URL set
#   prod-be: --env prod --backend-only --backend-port P
#   dev-be:  --backend-only --backend-port P
# serve.sh stop <label> [signal]  ; serve.sh wait <url> [secs]
# Env passthrough: anything exported (REFLEX_REDIS_URL, GRANIAN_WORKERS, REFLEX_BACKEND_START_METHOD, ...).
# Logs: $PM/logs/<label>.log ; pid file $PM/run/<label>.pid (the reflex CLI pid, own session via setsid).
set -u
: "${SB:?}"
PM=$SB/apps/verify_pm1
mkdir -p "$PM/logs" "$PM/run"
cmd=$1; shift
case "$cmd" in
  start)
    venv=$1; appdir=$2; label=$3; mode=$4; ports=$5; shift 5
    export REFLEX_TELEMETRY_ENABLED=${REFLEX_TELEMETRY_ENABLED:-false}
    export EXPECT_VENV=$venv
    case "$mode" in
      dev) fp=${ports%%:*}; bp=${ports##*:}; args=(run --frontend-port "$fp" --backend-port "$bp");;
      prod) export REFLEX_API_URL=http://localhost:$ports; args=(run --env prod --frontend-port "$ports" --backend-port "$ports");;
      prod-be) args=(run --env prod --backend-only --backend-port "$ports");;
      dev-be) args=(run --backend-only --backend-port "$ports");;
      *) echo "bad mode $mode"; exit 2;;
    esac
    : > "$PM/logs/$label.log"
    "$SB/envs/driver/bin/python" -I "$PM/scripts/launch.py" "$PM/logs/$label.log" "$appdir" "$SB/envs/$venv/bin/reflex" "${args[@]}" "$@" --loglevel debug > "$PM/run/$label.pid"
    echo "started $label pid=$(cat "$PM/run/$label.pid") mode=$mode ports=$ports log=$PM/logs/$label.log"
    ;;
  wait)
    url=$1; secs=${2:-360}; t0=$(date +%s)
    while :; do
      code=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' --max-time 3 "$url")
      if [ "$code" = 200 ]; then echo "up after $(( $(date +%s) - t0 ))s: $url"; exit 0; fi
      if [ $(( $(date +%s) - t0 )) -ge "$secs" ]; then echo "NOT UP after ${secs}s: $url (last $code)"; exit 1; fi
      sleep 1
    done
    ;;
  stop)
    label=$1; sig=${2:-TERM}; pid=$(cat "$PM/run/$label.pid" 2>/dev/null) || { echo "no pid for $label"; exit 1; }
    pgid=$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ')
    t0=$(date +%s.%N)
    kill -"$sig" "$pid" 2>/dev/null
    for i in $(seq 1 60); do kill -0 "$pid" 2>/dev/null || break; sleep 0.5; done
    if kill -0 "$pid" 2>/dev/null; then echo "STILL RUNNING $label pid=$pid after 30s (sig $sig)"; alive=1; else echo "$label exited $(printf '%.1f' "$(echo "$(date +%s.%N) - $t0" | bc)")s after SIG$sig"; alive=0; fi
    sleep 1
    left=$(ps -eo pid,ppid,pgid,stat,cmd | awk -v g="$pgid" '$3==g' | cut -c1-150)
    if [ -n "$left" ]; then echo "LEFTOVERS in pgid $pgid:"; echo "$left"; kill -KILL -- -"$pgid" 2>/dev/null; else echo "no leftovers in pgid $pgid"; fi
    ;;
  *) echo "usage"; exit 2;;
esac
