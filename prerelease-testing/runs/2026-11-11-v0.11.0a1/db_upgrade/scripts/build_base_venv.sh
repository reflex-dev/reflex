#!/usr/bin/env bash
# build_base_venv.sh <key> <appdir>: $SB/envs/db_upgrade-<key> = reflex[db]==0.10.1 + app requirements,
# constrained to the shared `prev` venv freeze (so every reflex sibling is the 0.10.1-era version). No --prerelease.
set -u
: "${SB:?}"; KEY=$1; APP=$2; W=$SB/apps/db_upgrade; V=$SB/envs/db_upgrade-$KEY
cd "$SB" || exit 2
rm -rf "$V"; uv --no-config venv "$V" --python 3.12 -q
grep -v -E '^(reflex|reflex\[db\])([<>=].*)?$' "$APP/requirements.txt" | grep -v '^\s*$' > "$W/freeze/$KEY-reqs.txt"
uv --no-config pip install --python "$V/bin/python" --only-binary :all: -c "$W/freeze/prev-constraints.txt" \
  'reflex[db]==0.10.1' -r "$W/freeze/$KEY-reqs.txt" 2>&1 | grep -v UV_NATIVE | tail -5
uv --no-config pip freeze --python "$V/bin/python" 2>/dev/null > "$W/freeze/$KEY-base.txt"
grep -E '^(reflex|sqlalchemy|sqlmodel|alembic|pydantic|aiosqlite)' "$W/freeze/$KEY-base.txt" | tr '\n' ' '; echo
