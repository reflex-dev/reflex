#!/usr/bin/env bash
# usage: run_typing.sh <new|prev> [file]   — pyright + mypy against the cluster's own typing venv
SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad
V=$SB/envs/events_await-typing-$1
F=${2:-typed_app.py}
cd "$SB/apps/events_await/typing" || exit 1
echo "### pyright ($1) $F"
"$V/bin/pyright" --pythonpath "$V/bin/python" "$F" 2>&1 | sed "s|$PWD/||" | grep -v '^$'
echo "### mypy ($1) $F"
"$V/bin/mypy" --python-executable "$V/bin/python" --config-file mypy.ini --cache-dir ".mypy_cache_$1" "$F" 2>&1
