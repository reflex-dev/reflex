#!/usr/bin/env bash
# Build the isolated, PyPI-only virtualenvs a pre-release pass uses, as $SB/envs/<name>.
#
# usage: NEW_VERSION=0.10.1a1 PREV_VERSION=0.10.0 scripts/bootstrap_envs.sh <scratch-dir> [--enterprise]
#        then: export SB=<scratch-dir>
#
# Venvs (names are what every fixture README and the agent brief refer to):
#   new     reflex[db]==$NEW_VERSION                               the version under test
#   prev    reflex[db]==$PREV_VERSION                              the previous release (before/after baseline)
#   ctrl-X  reflex[db]==X for each X in $CTRL_VERSIONS             positive controls (versions a finding reproduced on)
#   driver  playwright, httpx, websockets, pip                     browser drivers and HTTP probes
#   new-ent / prev-ent  (with --enterprise)                        + reflex-enterprise and oidc-provider-mock
#
# Enterprise: set ENT_WHEEL to a user-supplied offline wheel (bypasses the login gate; never commit it), or
# ENT_SPEC to a PyPI requirement such as 'reflex-enterprise[mcp]==0.9.7' (run enterprise apps with CI=true).
# Alphas need pre-release resolution; PYDANTIC_PIN (default 'pydantic<2.15') keeps the transitive graph user-like.
# Never run uv with a reflex checkout as the working directory: its pyproject's exclude-newer window hides fresh
# packages, and the checkout would shadow the installed package. Existing venvs are reused; delete one to rebuild it.
set -euo pipefail
SB="${1:?usage: NEW_VERSION=... PREV_VERSION=... bootstrap_envs.sh <scratch-dir> [--enterprise]}"; ENT="${2:-}"
: "${NEW_VERSION:?set NEW_VERSION, e.g. 0.10.1a1}"
: "${PREV_VERSION:?set PREV_VERSION, e.g. 0.10.0}"
PY="${PYTHON_VERSION:-3.12}"
PYDANTIC_PIN="${PYDANTIC_PIN:-pydantic<2.15}"
mkdir -p "$SB/envs" "$SB/apps" "$SB/logs" "$SB/downloads"; cd "$SB"

mk() { # name, pip args...
  local name="$1"; shift
  [ -x "$SB/envs/$name/bin/python" ] && return 0
  uv --no-config venv -q --python "$PY" "$SB/envs/$name"
  uv --no-config pip install -q --python "$SB/envs/$name/bin/python" --prerelease=allow "$@"
}
# greenlet must arrive through the db extra (N-001): never add it by hand to new/prev.
# The published reflex wheel pins reflex-base to its own version, so reflex[db]==X brings the matching reflex-base.
mk new  "reflex[db]==$NEW_VERSION"  "$PYDANTIC_PIN"
# PREV_EXTRAS adds packages to prev only, e.g. PREV_EXTRAS=greenlet when PREV is a 0.9.x release (N-001 on 0.9.x).
# shellcheck disable=SC2086
mk prev "reflex[db]==$PREV_VERSION" "$PYDANTIC_PIN" ${PREV_EXTRAS:-}
for v in ${CTRL_VERSIONS:-}; do
  # 0.9.x controls need greenlet by hand (SQLAlchemy 2.1 dropped it and 0.9's db extra predates #7466).
  mk "ctrl-$v" "reflex[db]==$v" "$PYDANTIC_PIN" greenlet
done
mk driver playwright httpx websockets pip
[ -x /opt/pw-browsers/chromium ] || "$SB/envs/driver/bin/python" -m playwright install chromium >/dev/null 2>&1 \
  || echo "playwright chromium install failed; set the Chromium path manually"

if [ "$ENT" = "--enterprise" ]; then
  ENT_REQ="${ENT_WHEEL:-${ENT_SPEC:-}}"
  [ -n "$ENT_REQ" ] || { echo "--enterprise needs ENT_WHEEL=<offline wheel path> or ENT_SPEC=<requirement>"; exit 3; }
  case "$ENT_REQ" in *.whl) [ -f "$ENT_REQ" ] || { echo "enterprise wheel missing: $ENT_REQ"; exit 3; }; ENT_REQ="$ENT_REQ[mcp]";; esac
  mk new-ent  "reflex[db]==$NEW_VERSION"  "$PYDANTIC_PIN" "$ENT_REQ" oidc-provider-mock
  mk prev-ent "reflex[db]==$PREV_VERSION" "$PYDANTIC_PIN" "$ENT_REQ" oidc-provider-mock
fi

for e in new prev $(for v in ${CTRL_VERSIONS:-}; do echo "ctrl-$v"; done) new-ent prev-ent; do
  [ -x "$SB/envs/$e/bin/python" ] || continue
  echo "== $e: $(cd "$SB" && "$SB/envs/$e/bin/python" -I -c 'import importlib.metadata as m
out = []
for p in ("reflex", "reflex-base", "reflex-enterprise", "sqlalchemy", "greenlet", "pydantic"):
    try: out.append(f"{p}={m.version(p)}")
    except m.PackageNotFoundError: out.append(f"{p}=-")
print(" ".join(out))')"
done
echo "export SB=$SB"
