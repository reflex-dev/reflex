#!/usr/bin/env bash
# N-001 / F-005 end to end: the migrated dbcli app (inst/run/dbcli-<k>) in PROD on port 3602: add x2, reload, both rows rendered.
set -u
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; I=$SB/apps/a5_upgrade_ent/inst; P=3602
for k in ${@:-pip314 uv311}; do
  V=$SB/envs/a5_upgrade_ent-n001-$k; A=$I/run/dbcli-$k; LOG=$I/logs/dbcli-prod-$k.log
  cd $A || continue
  REFLEX_TELEMETRY_ENABLED=false REFLEX_API_URL=http://localhost:$P setsid $V/bin/reflex run --env prod --frontend-port $P --backend-port $P --loglevel debug > $LOG 2>&1 < /dev/null &
  PID=$!; start=$(date +%s)
  until [ "$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:$P/)" = 200 ] && [ "$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:$P/ping)" = 200 ]; do
    kill -0 $PID 2>/dev/null || { echo "$k: server died"; tail -20 $LOG; break; }; [ $(( $(date +%s) - start )) -gt 420 ] && { echo "$k: TIMEOUT"; break; }; sleep 3; done
  echo "$k prod up after $(( $(date +%s) - start ))s"
  NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python -I $I/scripts/drive_app.py http://localhost:$P/ \
    --actions '[{"click":"#add"},{"click":"#add"},{"expect_text":"note 2"},{"goto":"http://localhost:'$P'/"},{"wait":1500},{"expect_text":"note 2"}]' \
    --report $I/logs/dbcli-prod-$k.json > $I/logs/dbcli-prod-$k.drive.txt 2>&1; echo "$k drive rc=$? $(tail -1 $I/logs/dbcli-prod-$k.drive.txt | cut -c1-200)"
  echo "$k rows: $($SB/envs/driver/bin/python -I -c "import sqlite3,sys; print(sqlite3.connect(sys.argv[1]).execute('select count(*) from note').fetchone()[0])" $A/reflex.db) tracebacks=$(grep -c Traceback $LOG)"
  kill -TERM $PID; for i in $(seq 1 20); do kill -0 $PID 2>/dev/null || break; sleep 0.5; done; kill -KILL -- -$PID 2>/dev/null
  for lp in $(lsof -nP -iTCP:$P -sTCP:LISTEN -t 2>/dev/null); do kill -KILL $lp; done
done
