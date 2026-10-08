#!/usr/bin/env bash
# N-001 original repro + F-005 fresh-db migrations on every db venv: greenlet_probe, reflex db init / makemigrations / migrate / makemigrations noop.
set -u
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a5_upgrade_ent/inst
for k in ${@:-uv311 uv314 pip311 pip314}; do
  V=$SB/envs/a5_upgrade_ent-n001-$k; A=$W/run/dbcli-$k; rm -rf $A; mkdir -p $W/run; cp -r $W/apps/dbcli $A
  echo "=== $k"
  (cd $A && $V/bin/python -I $W/scripts/greenlet_probe.py /envs/a5_upgrade_ent-n001-$k/)
  for c in "init" "makemigrations --message init" "migrate" "makemigrations --message noop"; do
    (cd $A && REFLEX_TELEMETRY_ENABLED=false $V/bin/reflex db $c > $W/logs/db-$k-${c%% *}.log 2>&1; echo "reflex db $c rc=$? $(grep -ciE 'error|traceback' $W/logs/db-$k-${c%% *}.log) error-lines")
  done
  echo "  versions: $(ls $A/alembic/versions | grep -c '\.py$') files; tables: $($SB/envs/driver/bin/python -I -c "import sqlite3,sys; print(sorted(r[0] for r in sqlite3.connect(sys.argv[1]).execute(\"select name from sqlite_master where type='table'\")))" $A/reflex.db)"
done
