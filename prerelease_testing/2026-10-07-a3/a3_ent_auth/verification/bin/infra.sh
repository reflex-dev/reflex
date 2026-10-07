#!/usr/bin/env bash
# Usage: infra.sh start|stop   -- redis-server :8629 + oidc-provider-mock (scripts/mock_oidc.py, a3-ent venv) :8638
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/verify_ent_auth; R=$W/run
case $1 in
  start)
    setsid redis-server --port 8629 --bind 127.0.0.1 --save '' --appendonly no > $W/logs/redis.log 2>&1 < /dev/null &
    echo $! > $R/redis.pid
    (cd $W/run && MOCK_OIDC_PORT=8638 MOCK_OIDC_MAX_AGE=${2:-3600} setsid $SB/envs/a3-ent/bin/python $W/scripts/mock_oidc.py >> $W/logs/mock-oidc.log 2>&1 < /dev/null & echo $! > $R/oidc.pid)
    for i in $(seq 1 40); do curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:8638/.well-known/openid-configuration | grep -q 200 && break; sleep 0.5; done
    redis-cli -p 8629 ping; curl -s --noproxy '*' http://localhost:8638/.well-known/openid-configuration | head -c 200; echo;;
  stop)
    [ -s $R/oidc.pid ] && kill $(cat $R/oidc.pid) 2>/dev/null; rm -f $R/oidc.pid
    redis-cli -p 8629 shutdown nosave 2>/dev/null; rm -f $R/redis.pid; echo stopped-infra;;
esac
