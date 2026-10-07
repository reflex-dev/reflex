#!/usr/bin/env bash
# F-006: in-place upgrade matrix from a seeded 0.9.12 environment to 0.10.0a2.
# usage: install_matrix_upgrade.sh <label> <tool: pip|uv> <extra args to the 2nd install...>
# env: SB (scratchpad), W (work dir). Venv: $SB/envs/rdi-up-<label>
set -u
label=$1; tool=$2; shift 2
E=$SB/envs/rdi-up-$label
rm -rf "$E"; cd "$SB"
uv --no-config venv --seed --python 3.12 "$E" >/dev/null 2>&1
if [ "$tool" = pip ]; then
  "$E/bin/python" -m pip install -q 'reflex==0.9.12' >/dev/null 2>&1
  "$E/bin/python" -m pip freeze > "$W/freeze/up-$label-before.txt"
  echo "+ pip install $*"
  "$E/bin/python" -m pip install "$@" > "$W/logs/up-$label.log" 2>&1; rc=$?
  "$E/bin/python" -m pip freeze > "$W/freeze/up-$label-after.txt"
else
  uv --no-config pip install -q --python "$E/bin/python" 'reflex==0.9.12' >/dev/null 2>&1
  uv --no-config pip freeze --python "$E/bin/python" 2>/dev/null > "$W/freeze/up-$label-before.txt"
  echo "+ uv pip install $*"
  uv --no-config pip install --python "$E/bin/python" "$@" > "$W/logs/up-$label.log" 2>&1; rc=$?
  uv --no-config pip freeze --python "$E/bin/python" 2>/dev/null > "$W/freeze/up-$label-after.txt"
fi
echo "rc=$rc"
echo "--- reflex* diff (before -> after):"
diff <(grep -i '^reflex\|sqlmodel\|pydantic' "$W/freeze/up-$label-before.txt") <(grep -i '^reflex\|sqlmodel\|pydantic' "$W/freeze/up-$label-after.txt") | grep '^[<>]' | sort -k2 | head -60
echo "--- reflex* after:"
grep -i '^reflex' "$W/freeze/up-$label-after.txt" | tr '\n' ' '; echo
