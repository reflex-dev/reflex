#!/usr/bin/env bash
# Enterprise auth spot check on <venv> (default a4-ent = reflex 0.10.0a4 + enterprise 0.9.7a5 offline wheel), label <L>.
# 1) N-032 verifier probes (vauth app, dev, Redis): vdrv stale/away/xtab x3 + race summary, hunt loads/relogin.
# 2) explorer app entauth (dev, Redis): full auth cycle / pubnav / twotab / xtab, xtab_probe x5, stale_hash_probe x3, hydration_token_probe.
# 3) 10-05 a4 auth matrix (dev, memory) + MCP checks.
# Usage: seq_ent_auth.sh [venv] [label] [parts=123]
set -u
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; E=$SB/apps/a4_upgrade_ent/ent/auth
V=${1:-a4-ent}; L=${2:-a4e}; PARTS=${3:-123}
DRV="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 timeout 1200 $SB/envs/driver/bin/python"
mkdir -p $E/run $E/logs $E/shots
$E/bin/infra.sh start
if [[ $PARTS == *1* ]]; then
  echo "### part 1 vauth_$L dev redis $(date +%T)"; redis-cli -p 8629 flushall
  [ -d $E/vauth_$L ] || { mkdir -p $E/vauth_$L; cp -r $E/src/vauth/* $E/vauth_$L/; }
  $E/bin/start_app.sh $V vauth_$L dev $E/logs/$L-dev-redis.server.log; head -1 $E/logs/$L-dev-redis.server.log
  $E/bin/wait_ready.sh http://localhost:3620/ http://localhost:8620 420 || { $E/bin/stop_app.sh; $E/bin/infra.sh stop; exit 1; }
  cd $E/drivers
  for m in stale away xtab; do $DRV vdrv.py $m http://localhost:3620 $L-dev-redis 3 2>&1 | tail -n 4 | cut -c1-300; done
  $DRV race.py ../logs/$L-dev-redis-xtab.json 2>&1 | tail -n 3 | cut -c1-300
  for m in loads relogin; do $DRV hunt.py $m http://localhost:3620 $L-dev-redis 2 2>&1 | tail -n 3 | cut -c1-300; done
  $E/bin/stop_app.sh
  echo "server log $L-dev-redis: tracebacks=$(grep -c Traceback $E/logs/$L-dev-redis.server.log) TypeError=$(grep -c TypeError $E/logs/$L-dev-redis.server.log)"
fi
if [[ $PARTS == *2* ]]; then
  echo "### part 2 entauth_$L dev redis $(date +%T)"; redis-cli -p 8629 flushall
  [ -d $E/entauth_$L ] || { mkdir -p $E/entauth_$L; cp -r $E/src/entauth/* $E/entauth_$L/; }
  VENV=$V APP_DIR=entauth_$L $E/scripts/start_app.sh dev $E/logs/entauth-dev-redis-$L.log
  $E/bin/wait_ready.sh http://localhost:3620/ http://localhost:8620 420 || { $E/bin/stop_app.sh; $E/bin/infra.sh stop; exit 1; }
  cd $E/scripts
  $DRV drive_auth_redis.py http://localhost:3620 $L-dev-redis cycle,pubnav,twotab,xtab 2>&1 | tail -n 6 | cut -c1-300
  $DRV xtab_probe.py http://localhost:3620 $L-dev-redis-rep 5 2>&1 | tail -n 3 | cut -c1-300
  $DRV stale_hash_probe.py http://localhost:3620 $L-dev-redis 3 2>&1 | tail -n 3 | cut -c1-300
  $DRV hydration_token_probe.py http://localhost:3620 $L-dev-redis 2>&1 | tail -n 4 | cut -c1-300
  $E/bin/stop_app.sh
  echo "server log entauth $L: tracebacks=$(grep -c Traceback $E/logs/entauth-dev-redis-$L.log) TypeError=$(grep -c TypeError $E/logs/entauth-dev-redis-$L.log)"
fi
if [[ $PARTS == *3* ]]; then
  echo "### part 3 a4 auth matrix $(date +%T)"
  $E/scripts/a4_matrix.sh $V $L 2>&1 | tail -n 14 | cut -c1-300
  $E/bin/a4_tally.sh $L
fi
$E/bin/infra.sh stop
echo "### ent auth done $(date +%T)"
