#!/usr/bin/env bash
# N-001 original repro + F-005 fresh-db migrations on every n001 db venv: greenlet_probe, reflex db init / makemigrations /
# migrate / makemigrations noop (expected: every rc 0, 0 error lines, 1 version file, tables alembic_version + note).
# Usage: dbcli.sh [key ...]   (default: uv311 uv314 pip311 pip314); app copies in inst/run/dbcli-<key>
set -u; . "$(dirname "$0")/../../bin/env.sh"; I=$(cd "$(dirname "$0")/.." && pwd); mkdir -p "$I/logs" "$I/run"
for k in ${@:-uv311 uv314 pip311 pip314}; do
  V=$SB/envs/$VENV_PREFIX-n001-$k; A=$I/run/dbcli-$k; rm -rf "$A"; cp -r "$I/apps/dbcli" "$A"
  echo "=== $k"
  (cd "$A" && "$V/bin/python" -I "$I/scripts/greenlet_probe.py" "/envs/$VENV_PREFIX-n001-$k/")
  for c in "init" "makemigrations --message init" "migrate" "makemigrations --message noop"; do
    (cd "$A" && "$V/bin/reflex" db $c > "$I/logs/db-$k-${c%% *}.log" 2>&1; echo "reflex db $c rc=$? $(grep -ciE 'error|traceback' "$I/logs/db-$k-${c%% *}.log") error-lines")
  done
  echo "  versions: $(ls "$A/alembic/versions" | grep -c '\.py$') files; tables: $("$DPY" -I -c "import sqlite3,sys; print(sorted(r[0] for r in sqlite3.connect(sys.argv[1]).execute(\"select name from sqlite_master where type='table'\")))" "$A/reflex.db")"
done
