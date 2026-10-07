#!/usr/bin/env bash
# F-005 reverse direction: env created with reflex[db]==0.9.11 + sqlmodel==0.0.44 (pre-2026-09-21 population),
# then upgraded in place to 0.10.0a2 with the given installer.
# usage: upgrade_sm044.sh <label> <pip|uv> <install args...>     env: SB, W
set -u
label=$1; tool=$2; shift 2
E=$SB/envs/rdi-sm044-$label
rm -rf "$E"; cd "$SB"
uv --no-config venv --seed --python 3.12 "$E" >/dev/null 2>&1
uv --no-config pip install -q --python "$E/bin/python" 'reflex[db]==0.9.11' 'sqlmodel==0.0.44' >/dev/null 2>&1
uv --no-config pip freeze --python "$E/bin/python" 2>/dev/null > "$W/freeze/16-sm044-$label-before.txt"
if [ "$tool" = pip ]; then
  echo "+ pip install $*"; "$E/bin/python" -m pip install "$@" > "$W/logs/16-sm044-$label-upgrade.log" 2>&1; rc=$?
else
  echo "+ uv pip install $*"; uv --no-config pip install --python "$E/bin/python" "$@" > "$W/logs/16-sm044-$label-upgrade.log" 2>&1; rc=$?
fi
uv --no-config pip freeze --python "$E/bin/python" 2>/dev/null > "$W/freeze/16-sm044-$label-after.txt"
echo "rc=$rc"
for f in before after; do echo -n "$f: "; grep -iE '^(reflex|reflex-base|sqlmodel|sqlalchemy|greenlet|alembic|pydantic)==' "$W/freeze/16-sm044-$label-$f.txt" | tr '\n' ' '; echo; done
