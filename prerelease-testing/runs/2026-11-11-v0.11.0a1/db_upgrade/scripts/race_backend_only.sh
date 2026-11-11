#!/usr/bin/env bash
# race_backend_only.sh <venv-key> <n>: n fresh copies of the 0.10.1 form-designer snapshot (legacy env.py),
# each started `reflex run --env prod --backend-only` with Redis + GRANIAN_WORKERS=4 (every worker imports the app,
# whose import-time rx.model.migrate() replaces env.py). Reports env.py/env.old state, tracebacks, /ping.
. "$(dirname "$0")/env.sh"; K=$1; N=${2:-3}
for i in $(seq 1 $N); do
  A=$W/combo/fd-race-$K-$i; rm -rf $A; cpapp $W/snap/fd-base $A
  L=$W/logs/race-$K-$i.server.log
  (cd $A && REFLEX_REDIS_URL=redis://localhost:8119 GRANIAN_WORKERS=4 setsid $(venv $K)/bin/reflex run --env prod --backend-only --backend-port 8101 --loglevel debug > $L 2>&1 < /dev/null & echo $! > $W/logs/$(basename $A).pid)
  for t in $(seq 1 40); do [ "$(http_code http://localhost:8101/ping)" = 200 ] && break; sleep 1; done
  sleep 6
  echo "run $i: ping=$(http_code http://localhost:8101/ping) env.py-is-template=$(cmp -s $A/alembic/env.py $(venv $K)/lib/python3.12/site-packages/reflex/.templates/alembic/env.py && echo yes || echo no) env.old-is-stock=$(cmp -s $A/alembic/env.old $W/snap/fd-base/alembic/env.py && echo yes || echo no/absent) workers=$(grep -c 'Started worker' $L) updated-msgs=$(grep -c 'Updated env.py' $L) tracebacks=$(grep -c Traceback $L) died=$(grep -cE 'Unexpected exit|died|Error' $L)"
  grep -E '^[A-Za-z.]+(Error|Exception):' $L | sort | uniq -c | head -5
  $W/scripts/stop.sh $A 8101 >/dev/null
done
