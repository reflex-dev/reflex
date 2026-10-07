#!/usr/bin/env bash
# env with the a1 full train (hosting-cli 0.1.73a1) from the 10-06 freeze, then upgrade to a2 with the given installer.
# usage: upgrade_hc073.sh <label> <pip|uv> <install args...>     env: SB, W
set -u
label=$1; tool=$2; shift 2
E=$SB/envs/rdi-hc073-$label; rm -rf "$E"; cd "$SB"
uv --no-config venv --seed --python 3.12 "$E" >/dev/null 2>&1
uv --no-config pip install -q --python "$E/bin/python" -r /home/user/reflex/prerelease_testing/2026-10-06/pymatrix_install/freeze/1b-pip-pre.txt >/dev/null 2>&1
uv --no-config pip freeze --python "$E/bin/python" 2>/dev/null > "$W/freeze/27-hc073-$label-before.txt"
if [ "$tool" = pip ]; then echo "+ pip install $*"; "$E/bin/python" -m pip install "$@" > "$W/logs/27-hc073-$label.log" 2>&1; rc=$?
else echo "+ uv pip install $*"; uv --no-config pip install --python "$E/bin/python" "$@" > "$W/logs/27-hc073-$label.log" 2>&1; rc=$?; fi
uv --no-config pip freeze --python "$E/bin/python" 2>/dev/null > "$W/freeze/27-hc073-$label-after.txt"
echo "rc=$rc"
for f in before after; do echo -n "$f: "; grep -iE '^(reflex|reflex-base|reflex-hosting-cli|reflex-build-sdk)==' "$W/freeze/27-hc073-$label-$f.txt" | tr '\n' ' '; echo; done
echo -n "pip check: "; "$E/bin/python" -m pip check 2>&1 | head -3 | tr '\n' ' '; echo
