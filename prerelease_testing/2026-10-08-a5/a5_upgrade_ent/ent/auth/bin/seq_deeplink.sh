#!/usr/bin/env bash
# reflex#7360 enterprise router probe (vauthd app, drivers/deeplink.py) on <venv> <label>: dev + Redis (3 reps), prod + Redis 1 worker (2 reps).
# Ports: dev 3620/8620, prod 8621, Redis 8629, mock IdP 8638 (bin/infra.sh).
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; E=$SB/apps/a5_upgrade_ent/ent/auth
V=${1:-a5-ent}; L=${2:-a5e}; MODES=${3:-dev,prod}
DRV="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 timeout 900 $SB/envs/driver/bin/python"
mkdir -p $E/run $E/logs $E/shots
[ -d $E/vauthd_$L ] || { mkdir -p $E/vauthd_$L; cp -r $E/src/vauthd/* $E/vauthd_$L/; }
$E/bin/infra.sh start
if [[ $MODES == *dev* ]]; then
  redis-cli -p 8629 flushall
  rm -f $E/logs/$L-dl-dev-redis.audit.jsonl; VAUTHD_AUDIT_FILE=$E/logs/$L-dl-dev-redis.audit.jsonl $E/bin/start_app.sh $V vauthd_$L dev $E/logs/$L-dl-dev-redis.server.log; head -1 $E/logs/$L-dl-dev-redis.server.log
  $E/bin/wait_ready.sh http://localhost:3620/ http://localhost:8620 420 && (cd $E/drivers && $DRV deeplink.py http://localhost:3620 $L-dl-dev-redis 3 2>&1 | tail -n 4 | cut -c1-600)
  $E/bin/stop_app.sh
  echo "server log $L-dl-dev-redis: tracebacks=$(grep -c Traceback $E/logs/$L-dl-dev-redis.server.log) deprecate=$(grep -ci 'deprecat' $E/logs/$L-dl-dev-redis.server.log)"; $SB/envs/driver/bin/python -I $E/drivers/audit_routes.py $E/logs/$L-dl-dev-redis.audit.jsonl
fi
if [[ $MODES == *prod* ]]; then
  redis-cli -p 8629 flushall
  rm -f $E/logs/$L-dl-prod-redis-1w.audit.jsonl; VAUTHD_AUDIT_FILE=$E/logs/$L-dl-prod-redis-1w.audit.jsonl GRANIAN_WORKERS=1 $E/bin/start_app.sh $V vauthd_$L prod $E/logs/$L-dl-prod-redis-1w.server.log
  $E/bin/wait_ready.sh http://localhost:8621/ http://localhost:8621 600 && (cd $E/drivers && $DRV deeplink.py http://localhost:8621 $L-dl-prod-redis-1w 2 2>&1 | tail -n 3 | cut -c1-600)
  $E/bin/stop_app.sh
  echo "server log $L-dl-prod-redis-1w: tracebacks=$(grep -c Traceback $E/logs/$L-dl-prod-redis-1w.server.log) deprecate=$(grep -ci 'deprecat' $E/logs/$L-dl-prod-redis-1w.server.log)"; $SB/envs/driver/bin/python -I $E/drivers/audit_routes.py $E/logs/$L-dl-prod-redis-1w.audit.jsonl
fi
$E/bin/infra.sh stop
echo "### deeplink $L done $(date +%T)"
