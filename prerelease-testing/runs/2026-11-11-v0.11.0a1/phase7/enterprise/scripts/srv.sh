#!/usr/bin/env bash
# Phase 7 enterprise server helper (ports: fe 3380, be/single 8380).
# srv.sh start <venv ent-0912|ent-0911|...> <dev|prod> <src dir> <label> [ENV=VAL ...]
#   venv is looked up under $P7 (p7/envs) first, then $SB/envs.
#   prod: single port 8380 (REFLEX_API_URL=http://localhost:8380), REFLEX_ACCESS_TOKEN read from $SB/secrets (never written to a file).
#   dev : frontend 3380, backend 8380.
#   The app is copied (without .web) to $W/runs/<label> and run from there; log $W/logs/<label>.log
#   NOFRESH=1 keeps an existing run dir (.web reuse).
# srv.sh stop     stop the process group started last
set -u
SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad
W=$SB/p7/work/ent; PIDF=$W/run/pgid; mkdir -p $W/run $W/logs $W/runs
venv() { for d in $SB/p7/envs/$1 $W/envs/$1 $SB/envs/$1; do [ -x $d/bin/reflex ] && { echo $d; return; }; done; echo $SB/envs/$1; }
case $1 in
  stop)
    [ -s "$PIDF" ] || { echo nothing; exit 0; }
    G=$(cat $PIDF); kill -INT -- -$G 2>/dev/null
    for i in $(seq 1 30); do pgrep -g $G >/dev/null || break; sleep 0.5; done
    pgrep -g $G >/dev/null && { kill -KILL -- -$G 2>/dev/null; echo "killed -9 $G"; }
    : > $PIDF; echo stopped;;
  start)
    V=$2; MODE=$3; SRC=$4; L=$5; shift 5; VE=$(venv $V)
    for p in 3380 8380; do curl -s --noproxy '*' -o /dev/null -m 2 http://localhost:$p/ && { echo "port $p busy"; exit 2; }; done
    R=$W/runs/$L; [ "${NOFRESH:-0}" = 1 ] || rm -rf $R; mkdir -p $R
    (cd $SRC && tar --exclude=.web --exclude=__pycache__ --exclude='*.db' --exclude=.states -cf - .) | (cd $R && tar -xf -)
    LOG=$W/logs/$L.log
    if [ $MODE = prod ]; then FP=8380; X=(--env prod); A=(REFLEX_API_URL=http://localhost:8380 REFLEX_ACCESS_TOKEN="$(cat $SB/secrets/reflex_access_token)"); else FP=3380; X=(); A=(); fi
    cd $R; export VE_VENV=$VE
    env CI=true REFLEX_TELEMETRY_ENABLED=false GRANIAN_WORKERS=1 "${A[@]}" "$@" \
      setsid $VE/bin/reflex run --frontend-port $FP --backend-port 8380 "${X[@]}" > $LOG 2>&1 < /dev/null &
    P=$!; sleep 1; ps -o pgid= -p $P | tr -d ' ' > $PIDF
    for i in $(seq 1 200); do
      c=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' -m 5 http://localhost:$FP/ 2>/dev/null)
      b=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' -m 5 http://localhost:8380/ping 2>/dev/null)
      [ "$c" = 200 ] && [ "$b" = 200 ] && { echo "[$L] ready after $((i*2))s"; exit 0; }
      kill -0 $P 2>/dev/null || { echo "[$L] server exited"; exit 1; }
      sleep 2
    done; echo "[$L] not ready (fe=$c be=$b)"; exit 1;;
esac
