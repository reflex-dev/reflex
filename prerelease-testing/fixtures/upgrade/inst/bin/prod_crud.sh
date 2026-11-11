#!/usr/bin/env bash
# N-001 / F-005 end to end: the migrated dbcli app (inst/run/dbcli-<key>, from dbcli.sh) in PROD on one port: add x2, reload,
# both rows rendered, 2 rows in reflex.db, 0 tracebacks. Usage: prod_crud.sh [key ...] (default pip314 uv311); port P (3506)
set -u; . "$(dirname "$0")/../../bin/env.sh"; I=$(cd "$(dirname "$0")/.." && pwd); P=${P:-3506}
for k in ${@:-pip314 uv311}; do
  V=$SB/envs/$VENV_PREFIX-n001-$k; A=$I/run/dbcli-$k; LOG=$I/logs/dbcli-prod-$k.log
  cd "$A" || continue
  REFLEX_API_URL=http://localhost:$P setsid "$V/bin/reflex" run --env prod --frontend-port $P --backend-port $P --loglevel debug > "$LOG" 2>&1 < /dev/null &
  PID=$!; start=$(date +%s)
  until [ "$(http_code http://localhost:$P/)" = 200 ] && [ "$(http_code http://localhost:$P/ping)" = 200 ]; do
    kill -0 $PID 2>/dev/null || { echo "$k: server died"; tail -20 "$LOG"; break; }; [ $(( $(date +%s) - start )) -gt 420 ] && { echo "$k: TIMEOUT"; break; }; sleep 3; done
  echo "$k prod up after $(( $(date +%s) - start ))s"
  cd "$SB"
  $DRV -I "$I/scripts/drive_app.py" http://localhost:$P/ \
    --actions '[{"click":"#add"},{"click":"#add"},{"expect_text":"note 2"},{"goto":"http://localhost:'$P'/"},{"wait":1500},{"expect_text":"note 2"}]' \
    --report "$I/logs/dbcli-prod-$k.json" > "$I/logs/dbcli-prod-$k.drive.txt" 2>&1; echo "$k drive rc=$? $(tail -1 "$I/logs/dbcli-prod-$k.drive.txt" | cut -c1-200)"
  echo "$k rows: $("$DPY" -I -c "import sqlite3,sys; print(sqlite3.connect(sys.argv[1]).execute('select count(*) from note').fetchone()[0])" "$A/reflex.db") tracebacks=$(grep -c Traceback "$LOG")"
  kill -TERM $PID; for i in $(seq 1 20); do kill -0 $PID 2>/dev/null || break; sleep 0.5; done; kill -KILL -- -$PID 2>/dev/null
  for lp in $(lsof -nP -iTCP:$P -sTCP:LISTEN -t 2>/dev/null); do kill -KILL $lp; done
done
