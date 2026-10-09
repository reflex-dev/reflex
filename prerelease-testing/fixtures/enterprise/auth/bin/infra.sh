#!/usr/bin/env bash
# Usage: infra.sh start|stop|restart-oidc [token_max_age_s=3600]
# redis-server on 8629 and the published oidc-provider-mock (scripts/mock_oidc.py, run by $IDP_VENV) on 8638
# (users alice "Alice Admin" groups admins+staff, bob "Bob Member").
. "$(dirname "$0")/../../lib.sh"; fx_sync auth; W=$WORK/auth; R=$W/run
start_redis() {
  setsid redis-server --port 8629 --bind 127.0.0.1 --save '' --appendonly no > "$W/logs/redis.log" 2>&1 < /dev/null &
  echo $! > "$R/redis.pid"
}
start_oidc() {
  venv_check "$IDP_VENV" || return 1
  cd "$W/run" || return 1
  MOCK_OIDC_MAX_AGE=${1:-3600} setsid "$SB/envs/$IDP_VENV/bin/python" "$W/scripts/mock_oidc.py" >> "$W/logs/mock-oidc-main.log" 2>&1 < /dev/null &
  echo $! > "$R/oidc.pid"
  for i in $(seq 1 40); do curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:8638/.well-known/openid-configuration | grep -q 200 && break; sleep 0.5; done
}
stop_oidc() {
  [ -s "$R/oidc.pid" ] && kill "$(cat "$R/oidc.pid")" 2>/dev/null; rm -f "$R/oidc.pid"
  for q in $(lsof -t -iTCP:8638 -sTCP:LISTEN 2>/dev/null); do kill "$q"; done  # setsid may fork: kill by port too
}
case $1 in
  start) start_redis; start_oidc "${2:-3600}"; sleep 1; redis-cli -p 8629 ping; echo "oidc pid $(cat "$R/oidc.pid") redis pid $(cat "$R/redis.pid")";;
  stop) stop_oidc; redis-cli -p 8629 shutdown nosave 2>/dev/null; rm -f "$R/redis.pid"; echo stopped-infra;;
  restart-oidc) stop_oidc; sleep 1; start_oidc "${2:-3600}"; echo "oidc restarted max_age=${2:-3600} pid $(cat "$R/oidc.pid")";;
  *) echo "usage: infra.sh start|stop|restart-oidc [max_age]"; exit 2;;
esac
