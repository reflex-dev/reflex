#!/usr/bin/env bash
# xc.sh start <venv> <dev|prod> <label> [ENV=VAL ...]   start the xcut app (copy in $SB/apps/enterprise/runs/xcut_<venv>)
# xc.sh stop                                           stop it (process group), wait until ports are free
# prod: single port 8380 (REFLEX_API_URL=http://localhost:8380); dev: 3380/8380.
# Account: ACCT=stub (default; fixtures account_stub on 127.0.0.1:8397) or ACCT=token ($SB/secrets/reflex_access_token).
# REDIS=1 -> REFLEX_REDIS_URL=redis://127.0.0.1:8399 (start redis with `xc.sh redis`). AUTH needs the IdP (`xc.sh idp`).
set -u
SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad
E=$SB/apps/enterprise; SRC=${XC_SRC:-$E/src/xcut}; PIDF=$E/run/xc.pgid; mkdir -p $E/run $E/logs
stop_group() {
  [ -s "$PIDF" ] || return 0
  G=$(cat "$PIDF"); kill -INT -- -$G 2>/dev/null
  for i in $(seq 1 30); do pgrep -g $G >/dev/null || break; sleep 0.5; done
  pgrep -g $G >/dev/null && { kill -TERM -- -$G 2>/dev/null; sleep 2; kill -KILL -- -$G 2>/dev/null; echo "had to kill pgid $G"; }
  : > "$PIDF"
}
case $1 in
  redis) setsid redis-server --port 8399 --bind 127.0.0.1 --save '' --appendonly no > $E/logs/redis.log 2>&1 < /dev/null & echo $! > $E/run/redis.pid; sleep 1; redis-cli -p 8399 ping;;
  redis-stop) redis-cli -p 8399 shutdown nosave; rm -f $E/run/redis.pid;;
  idp) cd $E/run && IDP_VENV=new-ent MOCK_OIDC_PORT=8398 setsid $SB/envs/new-ent/bin/python -I $E/fx/auth/scripts/mock_oidc.py > $E/logs/idp.log 2>&1 < /dev/null & echo $! > $E/run/idp.pid
       for i in $(seq 1 40); do curl -s --noproxy '*' -o /dev/null http://localhost:8398/.well-known/openid-configuration && break; sleep 0.5; done; echo idp up;;
  idp-stop) kill $(cat $E/run/idp.pid) 2>/dev/null; for q in $(lsof -t -iTCP:8398 -sTCP:LISTEN 2>/dev/null); do kill $q; done;;
  stub) QA_FIXTURE_TOKEN=qa-fixture-token QA_ACCOUNT_AUDIT=$E/logs/account-stub.jsonl QA_ACCOUNT_PORT=8397 setsid $SB/envs/driver/bin/python -I $E/fx/account_stub.py > $E/logs/account-stub.log 2>&1 < /dev/null & echo $! > $E/run/stub.pid; sleep 1;;
  stub-stop) kill $(cat $E/run/stub.pid) 2>/dev/null;;
  stop) stop_group; for p in 3380 8380; do lsof -iTCP:$p -sTCP:LISTEN -nP >/dev/null 2>&1 && echo "still listening $p"; done; echo stopped;;
  start)
    VENV=$2; MODE=$3; LABEL=$4; shift 4
    for p in 3380 8380; do curl -s --noproxy '*' -o /dev/null -m 2 http://localhost:$p/ && { echo "port $p busy"; exit 2; }; done
    RUN=$E/runs/$(basename $SRC)_${VENV//-/}; mkdir -p $RUN
    (cd $SRC && tar --exclude=.web --exclude=__pycache__ -cf - .) | (cd $RUN && tar -xf -)
    LOG=$E/logs/xc_${LABEL}.log; : > $E/logs/xc_${LABEL}.life.jsonl; : > $E/logs/xc_${LABEL}.run.jsonl
    if [ $MODE = prod ]; then FP=8380; BP=8380; EXTRA=(--env prod); APIURL=http://localhost:8380; else FP=3380; BP=8380; EXTRA=(); APIURL=; fi
    ACCTENV=()
    if [ $MODE = prod ]; then
      if [ "${ACCT:-stub}" = token ]; then ACCTENV=(REFLEX_ACCESS_TOKEN="$(cat $SB/secrets/reflex_access_token)")
      else curl -s --noproxy '*' -o /dev/null http://127.0.0.1:8397/ || $0 stub; ACCTENV=(REFLEX_ACCESS_TOKEN=qa-fixture-token REFLEX_CLOUD_BACKEND_URL=http://127.0.0.1:8397); fi
    fi
    RED=(); [ "${REDIS:-0}" = 1 ] && RED=(REFLEX_REDIS_URL=redis://127.0.0.1:8399)
    echo "[xc.sh] $(date -u +%FT%TZ) venv=$VENV mode=$MODE label=$LABEL acct=${ACCT:-stub} redis=${REDIS:-0} extra=$*" > $LOG
    cd $RUN
    env CI=true REFLEX_TELEMETRY_ENABLED=false XC_EXPECT_VENV=$VENV XC_FP=$FP XC_BP=$BP ${APIURL:+REFLEX_API_URL=$APIURL} \
      XC_LIFELOG=$E/logs/xc_${LABEL}.life.jsonl XC_RUNLOG=$E/logs/xc_${LABEL}.run.jsonl \
      OIDC_ISSUER_URI=http://localhost:8398 OIDC_CLIENT_ID=reflex-integration-test OIDC_CLIENT_SECRET=reflex-integration-test-secret AUTHLIB_INSECURE_TRANSPORT=1 \
      "${ACCTENV[@]}" "${RED[@]}" "$@" \
      setsid $SB/envs/$VENV/bin/reflex run --frontend-port $FP --backend-port $BP "${EXTRA[@]}" --loglevel debug >> $LOG 2>&1 < /dev/null &
    PID=$!; sleep 1; ps -o pgid= -p $PID | tr -d ' ' > $PIDF
    for i in $(seq 1 180); do
      c=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' -m 5 http://localhost:$FP/ 2>/dev/null); b=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' -m 5 http://localhost:$BP/ping 2>/dev/null)
      [ "$c" = 200 ] && [ "$b" = 200 ] && { echo "ready after $((i*2))s"; exit 0; }
      kill -0 $PID 2>/dev/null || { echo "server exited"; tail -30 $LOG; exit 1; }
      sleep 2
    done; echo "not ready"; tail -30 $LOG; exit 1;;
esac
