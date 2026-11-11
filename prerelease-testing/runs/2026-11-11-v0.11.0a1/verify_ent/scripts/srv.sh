#!/usr/bin/env bash
# verify_ent server helper (ports: fe 3880-3895, be 8880-8895).
# srv.sh start <venv vent-new|vent-prev> <dev|prod> <src dir> <label> [ENV=VAL ...]
#   prod: single port 8880 (REFLEX_API_URL=http://localhost:8880), REFLEX_ACCESS_TOKEN from $SB/secrets (never written to a file).
#   dev : frontend 3880, backend 8880.
#   The app is copied (without .web) to $SB/apps/verify_ent/runs/<label> and run from there; log $SB/apps/verify_ent/logs/<label>.log
# srv.sh stop     stop the process group started last
set -u
SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad
W=$SB/apps/verify_ent; PIDF=$W/run/pgid; mkdir -p $W/run $W/logs $W/runs
case $1 in
  stop)
    [ -s "$PIDF" ] || { echo nothing; exit 0; }
    G=$(cat $PIDF); kill -INT -- -$G 2>/dev/null
    for i in $(seq 1 30); do pgrep -g $G >/dev/null || break; sleep 0.5; done
    pgrep -g $G >/dev/null && { kill -KILL -- -$G 2>/dev/null; echo "killed -9 $G"; }
    : > $PIDF; echo stopped;;
  start)
    V=$2; MODE=$3; SRC=$4; L=$5; shift 5
    for p in 3880 8880; do curl -s --noproxy '*' -o /dev/null -m 2 http://localhost:$p/ && { echo "port $p busy"; exit 2; }; done
    R=$W/runs/$L; mkdir -p $R; (cd $SRC && tar --exclude=.web --exclude=__pycache__ --exclude='*.db' -cf - .) | (cd $R && tar -xf -)
    LOG=$W/logs/$L.log
    if [ $MODE = prod ]; then FP=8880; X=(--env prod); A=(REFLEX_API_URL=http://localhost:8880 REFLEX_ACCESS_TOKEN="$(cat $SB/secrets/reflex_access_token)"); else FP=3880; X=(); A=(); fi
    cd $R; export VE_VENV=$SB/envs/$V
    env CI=true REFLEX_TELEMETRY_ENABLED=false GRANIAN_WORKERS=1 "${A[@]}" "$@" \
      setsid $SB/envs/$V/bin/reflex run --frontend-port $FP --backend-port 8880 "${X[@]}" > $LOG 2>&1 < /dev/null &
    P=$!; sleep 1; ps -o pgid= -p $P | tr -d ' ' > $PIDF
    for i in $(seq 1 180); do
      c=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' -m 5 http://localhost:$FP/ 2>/dev/null)
      b=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' -m 5 http://localhost:8880/ping 2>/dev/null)
      [ "$c" = 200 ] && [ "$b" = 200 ] && { echo "[$L] ready after $((i*2))s"; exit 0; }
      kill -0 $P 2>/dev/null || { echo "[$L] server exited"; exit 1; }
      sleep 2
    done; echo "[$L] not ready (fe=$c be=$b)"; exit 1;;
esac
