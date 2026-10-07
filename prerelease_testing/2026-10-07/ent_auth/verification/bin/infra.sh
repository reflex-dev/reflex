#!/usr/bin/env bash
# Usage: infra.sh start|stop|status   -- redis :8739 + oidc-provider-mock :8738 (verifier ports)
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/verify_ent_auth_0
case "$1" in
start)
  cd $W
  setsid redis-server --port 8739 --save '' --appendonly no > $W/logs/redis.log 2>&1 &
  echo $! > $W/logs/redis.pid
  AUTHLIB_INSECURE_TRANSPORT=1 setsid $SB/envs/alpha2-ent/bin/oidc-provider-mock -p 8738 > $W/logs/mock_idp.log 2>&1 &
  echo $! > $W/logs/mock.pid
  sleep 2; $0 status ;;
stop)
  for f in redis mock; do [ -f $W/logs/$f.pid ] && kill $(cat $W/logs/$f.pid) 2>/dev/null; rm -f $W/logs/$f.pid; done
  sleep 1; $0 status ;;
status)
  lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | awk '$9 ~ /:(37[2-3][0-9]|87[2-3][0-9])$/ {print $1,$2,$9}' ;;
esac
