#!/usr/bin/env bash
# Usage: infra.sh start|stop|restart-oidc [max_age]
# redis-server on 8349 and the published oidc-provider-mock (scripts/mock_oidc.py) on 8358.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/ent_auth2
R=$W/run
start_redis() {
  setsid redis-server --port 8349 --bind 127.0.0.1 --save '' --appendonly no > $W/logs/redis.log 2>&1 < /dev/null &
  echo $! > $R/redis.pid
}
start_oidc() {
  cd $W/scripts
  MOCK_OIDC_MAX_AGE=${1:-3600} setsid $SB/envs/alpha2-ent/bin/python $W/scripts/mock_oidc.py >> $W/logs/mock-oidc-main.log 2>&1 < /dev/null &
  echo $! > $R/oidc.pid
  for i in $(seq 1 30); do curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:8358/.well-known/openid-configuration | grep -q 200 && break; sleep 0.5; done
}
stop_pidfile() { [ -s "$1" ] && kill "$(cat $1)" 2>/dev/null; rm -f "$1"; }
case $1 in
  start) start_redis; start_oidc "${2:-3600}"; sleep 1; redis-cli -p 8349 ping; echo "oidc pid $(cat $R/oidc.pid) redis pid $(cat $R/redis.pid)";;
  stop) stop_pidfile $R/oidc.pid; redis-cli -p 8349 shutdown nosave 2>/dev/null; stop_pidfile $R/redis.pid; echo stopped-infra;;
  restart-oidc) stop_pidfile $R/oidc.pid; sleep 1; start_oidc "${2:-3600}"; echo "oidc restarted max_age=${2:-3600} pid $(cat $R/oidc.pid)";;
esac
