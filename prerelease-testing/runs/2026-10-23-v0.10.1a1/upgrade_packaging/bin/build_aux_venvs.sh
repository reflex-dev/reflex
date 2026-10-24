#!/usr/bin/env bash
# Auxiliary venvs for the upgrade_packaging item (all PyPI, user-like pip semantics where it matters):
#   upgrade_packaging-nogl-new  : pip 'reflex==0.10.1a1' + sqlmodel + alembic (NO db extra, NO greenlet)  (#7440)
#   upgrade_packaging-nogl-prev : pip 'reflex==0.10.0'   + sqlmodel + alembic (baseline)
#   upgrade_packaging-pure-prev : uv  'reflex[db]==0.10.0' without any prerelease flag (pure 0.10.0 train baseline)
#   upgrade_packaging-tp        : tp/bin/build_venv.sh (0.10.1a1 + 22 third-party packages)
set -u
: "${SB:?}"; : "${W:?}"
cd "$SB"
E=$SB/envs
mk_pip() { # mk_pip <name> <spec...>
  local V=$E/upgrade_packaging-$1; shift; rm -rf "$V"
  uv --no-config venv -q --seed --python 3.12 "$V" 2>&1 | grep -v UV_NATIVE
  "$V/bin/python" -m pip install --disable-pip-version-check -q "$@" 2>&1 | tail -3
  "$V/bin/python" -m pip freeze 2>/dev/null | grep -E '^(reflex|sqlalchemy|sqlmodel|greenlet|alembic|pydantic)' | tr '\n' ' '; echo
}
echo "=== nogl-new $(date +%T)"; mk_pip nogl-new 'reflex==0.10.1a1' sqlmodel alembic
echo "=== nogl-prev $(date +%T)"; mk_pip nogl-prev 'reflex==0.10.0' sqlmodel alembic
echo "=== pure-prev $(date +%T)"; V=$E/upgrade_packaging-pure-prev; rm -rf "$V"
uv --no-config venv -q --python 3.12 "$V" 2>&1 | grep -v UV_NATIVE
uv --no-config pip install -q --python "$V/bin/python" 'reflex[db]==0.10.0' 2>&1 | grep -v UV_NATIVE | tail -3
uv --no-config pip freeze --python "$V/bin/python" 2>/dev/null | grep -E '^(reflex|pydantic|sqlalchemy)' | tr '\n' ' '; echo
echo "=== tp $(date +%T)"; TP_EXTRA='pydantic<2.15' bash "$W/tp/bin/build_venv.sh"
echo "=== done $(date +%T)"
