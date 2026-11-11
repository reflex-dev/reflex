#!/bin/bash
# Build a PyPI-only test venv for this area: reflex[db,testing]==<version> + pytest, pytest-mock, pytest-asyncio, numpy, pandas, playwright.
# Usage: bash build_venvs.sh <venv-name> <reflex-version> [python=3.12] [tp]
#   tp: also install the 22 third-party packages of downstream/packages.txt (+ authlib) for test_n039_fields.py DOWNSTREAM=1
#       and pytest/downstream/test_pkg_states.py.
# Add UV_PRERELEASE=allow for an alpha/rc. Freeze written to $W/logs/venv/freeze-<venv-name>.txt
. "$(cd "$(dirname "$0")" && pwd)/env.sh"
N=$1; VER=$2; PY=${3:-3.12}; MODE=${4:-}
[ -n "$N" ] && [ -n "$VER" ] || { echo "usage: build_venvs.sh <venv-name> <reflex-version> [python] [tp]"; exit 2; }
mkdir -p "$W/logs/venv"; cd "$SB" || exit 1
EXTRA=(); [ "$MODE" = tp ] && EXTRA=($(cat "$CS/downstream/packages.txt") authlib 'google-api-python-client>=2.184.0')
set -x
uv --no-config venv --python "$PY" "$SB/envs/$N" &&
uv --no-config pip install --python "$SB/envs/$N/bin/python" "reflex[db,testing]==$VER" \
  pytest pytest-mock pytest-asyncio numpy pandas 'playwright==1.63.0' "${EXTRA[@]}" &&
uv --no-config pip freeze --python "$SB/envs/$N/bin/python" > "$W/logs/venv/freeze-$N.txt"
