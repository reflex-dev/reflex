#!/usr/bin/env bash
# Enterprise auth suite on <venv> (default $ENT_NEW), label <L> (default new).
# part 1 N-032 verifier (vauth app, dev, Redis): vdrv stale/away/xtab x3 + race summary, hunt loads/relogin x2.
# part 2 explorer app entauth (dev, Redis): drive_auth_redis cycle,pubnav,twotab,xtab; xtab_probe x5; stale_hash_probe x3; hydration_token_probe.
# part 3 10-05 a4 auth matrix (dev, memory) + MCP OAuth + anonymous MCP (needs $ENT_DRV and a4auth/fetch_upstream.sh, see README).
# Usage: seq_ent_auth.sh [venv] [label] [parts=123]
set -u
. "$(dirname "$0")/../../lib.sh"; fx_sync auth; E=$WORK/auth; B=$FX/auth/bin
V=${1:-$ENT_NEW}; L=${2:-new}; PARTS=${3:-123}
DRV="$NP timeout 1200 $DRVPY"
"$B/infra.sh" start
if [[ $PARTS == *1* ]]; then
  echo "### part 1 vauth_$L dev redis $(date +%T)"; redis-cli -p 8629 flushall
  fx_app auth vauth vauth_$L
  "$B/start_app.sh" "$V" vauth_$L dev "$E/logs/$L-dev-redis.server.log"; head -1 "$E/logs/$L-dev-redis.server.log"
  "$B/wait_ready.sh" http://localhost:3620/ http://localhost:8620 420 || { "$B/stop_app.sh"; "$B/infra.sh" stop; exit 1; }
  cd "$E/drivers"
  for m in stale away xtab; do $DRV vdrv.py $m http://localhost:3620 $L-dev-redis 3 2>&1 | tail -n 4 | cut -c1-300; done
  $DRV race.py ../logs/$L-dev-redis-xtab.json 2>&1 | tail -n 3 | cut -c1-300
  for m in loads relogin; do $DRV hunt.py $m http://localhost:3620 $L-dev-redis 2 2>&1 | tail -n 3 | cut -c1-300; done
  "$B/stop_app.sh"
  echo "server log $L-dev-redis: tracebacks=$(grep -c Traceback "$E/logs/$L-dev-redis.server.log") TypeError=$(grep -c TypeError "$E/logs/$L-dev-redis.server.log")"
fi
if [[ $PARTS == *2* ]]; then
  echo "### part 2 entauth_$L dev redis $(date +%T)"; redis-cli -p 8629 flushall
  fx_app auth entauth entauth_$L
  VENV=$V APP_DIR=entauth_$L "$FX/auth/scripts/start_app.sh" dev "$E/logs/entauth-dev-redis-$L.log"
  "$B/wait_ready.sh" http://localhost:3620/ http://localhost:8620 420 || { "$B/stop_app.sh"; "$B/infra.sh" stop; exit 1; }
  cd "$E/scripts"
  $DRV drive_auth_redis.py http://localhost:3620 $L-dev-redis cycle,pubnav,twotab,xtab 2>&1 | tail -n 6 | cut -c1-300
  $DRV xtab_probe.py http://localhost:3620 $L-dev-redis-rep 5 2>&1 | tail -n 3 | cut -c1-300
  $DRV stale_hash_probe.py http://localhost:3620 $L-dev-redis 3 2>&1 | tail -n 3 | cut -c1-300
  $DRV hydration_token_probe.py http://localhost:3620 $L-dev-redis 2>&1 | tail -n 4 | cut -c1-300
  "$B/stop_app.sh"
  echo "server log entauth $L: tracebacks=$(grep -c Traceback "$E/logs/entauth-dev-redis-$L.log") TypeError=$(grep -c TypeError "$E/logs/entauth-dev-redis-$L.log")"
fi
if [[ $PARTS == *3* ]]; then
  echo "### part 3 a4 auth matrix $(date +%T)"
  "$FX/auth/scripts/a4_matrix.sh" "$V" "$L" 2>&1 | tail -n 14 | cut -c1-300
  "$B/a4_tally.sh" "$L"
fi
"$B/infra.sh" stop
echo "### ent auth done $(date +%T)"
