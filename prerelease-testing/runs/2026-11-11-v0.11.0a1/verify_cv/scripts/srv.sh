#!/usr/bin/env bash
# srv.sh start <label> <venv> <dev|prod> <appdir> <fport> <bport> [ENV=VAL ...] | srv.sh stop <label>
set -u
SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad
W=$SB/apps/verify_cv
cmd=$1; label=$2
in_range() { local p=$1; { [ "$p" -ge 3760 ] && [ "$p" -le 3775 ]; } || { [ "$p" -ge 8760 ] && [ "$p" -le 8775 ]; }; }
case $cmd in
start)
  venv=$3; mode=$4; appdir=$5; fp=$6; bp=$7; shift 7
  in_range "$fp" && in_range "$bp" || { echo "port outside range"; exit 4; }
  for p in $fp $bp; do
    if curl -s --noproxy '*' -o /dev/null --max-time 2 "http://localhost:$p/"; then echo "port $p busy"; exit 5; fi
  done
  cd "$appdir" || exit 3
  log=$W/logs/$label.log
  if [ "$mode" = prod ]; then envs=(REFLEX_API_URL=http://localhost:$fp); args=(--env prod --frontend-port "$fp" --backend-port "$fp")
  else envs=(); args=(--frontend-port "$fp" --backend-port "$bp"); fi
  setsid env REFLEX_TELEMETRY_ENABLED=false EXPECT_VENV="$venv" "${envs[@]}" "$@" "$SB/envs/$venv/bin/reflex" run "${args[@]}" > "$log" 2>&1 < /dev/null &
  pid=$!; echo "$pid" > "$W/logs/$label.pgid"
  for i in $(seq 1 180); do
    if ! kill -0 "$pid" 2>/dev/null; then echo "server exited early; tail:"; tail -30 "$log"; exit 6; fi
    code=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' --max-time 3 "http://localhost:$fp/")
    if [ "$code" != 000 ]; then echo "up ($code) after ${i}x2s pgid $pid log=$log"; exit 0; fi
    sleep 2
  done
  echo timeout; tail -30 "$log"; exit 7 ;;
stop)
  f=$W/logs/$label.pgid; [ -f "$f" ] || { echo "no pgid"; exit 0; }
  pg=$(cat "$f"); kill -INT -- -"$pg" 2>/dev/null
  for i in 1 2 3 4 5 6 7 8; do kill -0 -- -"$pg" 2>/dev/null || break; sleep 1; done
  kill -9 -- -"$pg" 2>/dev/null; rm -f "$f"; echo "stopped $label" ;;
esac
