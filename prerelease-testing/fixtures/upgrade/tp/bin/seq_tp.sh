#!/usr/bin/env bash
# reflex-local-auth demo (dev, prod, prod+Redis) and reflex-magic-link-auth demo (dev, prod with ML_FORCE_DEV=1) on <venv>
# (default $VENV_PREFIX-tp from build_venv.sh), each from a FRESH copy + fresh db; ports 3463/8463 (dev), 8467 (prod), redis 8469.
# Usage: seq_tp.sh [venv] [label]   (needs bin/stage.sh: the demo apps are fetched + patched into tp/apps)
# Then compares check by check (cmp_checks.py) and console anomalies (compare_console.py) with $CMP_DIR/<pkg>-<mode>.json
# (default tp/expected = the a5 pass, reflex 0.10.0a5; expected: local-auth 36/38 x3, magic-link 10/11 x2, 0 differing).
set -u
. "$(dirname "$0")/../../bin/env.sh"; TW=$(cd "$(dirname "$0")/.." && pwd)
V=${1:-$VENV_PREFIX-tp}; L=${2:-new}
D="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 timeout 900 $DPY"
mkdir -p $TW/out/local_auth $TW/out/magic_link $TW/logs $TW/run/$L
up() { # <run dir> <fe url> <be url>
  local pidf=$TW/pids/$(basename $1)-$V.pid
  $TW/bin/wait_up.sh $2 420 $pidf || return 1
  for i in $(seq 1 120); do curl -s --noproxy '*' -o /dev/null -w '%{http_code}' $3/ping | grep -q 200 && return 0; sleep 1; done; return 1
}
fresh() { # <app> <name> -> run dir with migrated fresh db
  local R=$TW/run/$L/$2; rm -rf $R; cp -r $TW/apps/$1 $R
  (cd $R && TP_EXPECT_VENV=$V $SB/envs/$V/bin/reflex db migrate > $TW/logs/$L-$2-migrate.log 2>&1; echo "migrate $2 rc=$?")
}
run_la() { # <mode dev|prod|prodredis>
  local m=$1 R=$TW/run/$L/la_$1
  fresh local_auth_demo la_$m
  if [ $m = dev ]; then
    $TW/bin/start_app.sh $V $R 3463 8463 $TW/logs/la-$L-$m.log --loglevel debug; up $R http://localhost:3463/ http://localhost:8463 || { echo "la $m NOT UP"; }
    B=http://localhost:3463
  else
    [ $m = prodredis ] && export REFLEX_REDIS_URL=redis://localhost:8469
    REFLEX_API_URL=http://localhost:8467 $TW/bin/start_app.sh $V $R 8467 8467 $TW/logs/la-$L-$m.log --env prod --loglevel debug; up $R http://localhost:8467/ http://localhost:8467 || echo "la $m NOT UP"
    unset REFLEX_REDIS_URL; B=http://localhost:8467
  fi
  (cd $TW/drivers && $D drive_local_auth.py $B $TW/out/local_auth $L-$m $R/reflex.db > $TW/out/local_auth/$L-$m-stdout.txt 2>&1); tail -n 3 $TW/out/local_auth/$L-$m-stdout.txt | cut -c1-220
  [ $m = prodredis ] && echo "redis keys: $(redis-cli -p 8469 dbsize)"
  $TW/bin/stop_app.sh $TW/pids/la_$m-$V.pid
}
run_ml() { # <mode dev|prod>
  local m=$1 R=$TW/run/$L/ml_$1
  fresh magic_link_auth_demo ml_$m
  if [ $m = dev ]; then
    $TW/bin/start_app.sh $V $R 3463 8463 $TW/logs/ml-$L-$m.log --loglevel debug; up $R http://localhost:3463/ http://localhost:8463 || echo "ml $m NOT UP"; B=http://localhost:3463
  else
    ML_FORCE_DEV=1 REFLEX_API_URL=http://localhost:8467 $TW/bin/start_app.sh $V $R 8467 8467 $TW/logs/ml-$L-$m.log --env prod --loglevel debug; up $R http://localhost:8467/ http://localhost:8467 || echo "ml $m NOT UP"; B=http://localhost:8467
  fi
  (cd $TW/drivers && $D drive_magic_link.py $B $TW/out/magic_link $L-$m $TW/logs/ml-$L-$m.log > $TW/out/magic_link/$L-$m-stdout.txt 2>&1); tail -n 3 $TW/out/magic_link/$L-$m-stdout.txt | cut -c1-220
  $TW/bin/stop_app.sh $TW/pids/ml_$m-$V.pid
}
setsid redis-server --port 8469 --bind 127.0.0.1 --save '' --appendonly no > $TW/logs/redis.log 2>&1 < /dev/null & RPID=$!
for m in ${LA_MODES-dev prod prodredis}; do echo "### la $m $(date +%T)"; run_la $m; done
for m in ${ML_MODES-dev prod}; do echo "### ml $m $(date +%T)"; run_ml $m; done
redis-cli -p 8469 shutdown nosave 2>/dev/null; kill $RPID 2>/dev/null
CMP=${CMP_DIR:-$TW/expected}
for d in local_auth magic_link; do
  [ $d = local_auth ] && modes=${LA_MODES-dev prod prodredis} || modes=${ML_MODES-dev prod}
  for m in $modes; do
    echo "--- cmp expected vs $L $d $m: $($DPY -I $TW/bin/cmp_checks.py $CMP/$d-$m.json $TW/out/$d/$L-$m-report.json | tr '\n' ' ')"
    $DPY -I $TW/bin/compare_console.py $CMP/$d-$m.json $TW/out/$d/$L-$m-report.json 2>&1 | head -8
  done
done
for f in $TW/logs/la-$L-*.log $TW/logs/ml-$L-*.log; do [ -f "$f" ] || continue; echo "$(basename $f): tracebacks=$(grep -c Traceback $f) TypeError=$(grep -c TypeError $f)"; done
echo "### tp done $(date +%T)"
