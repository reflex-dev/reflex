#!/usr/bin/env bash
# Build the isolated, PyPI-only virtualenvs a pre-release pass uses, as $SB/envs/<name>.
#
# usage: NEW_VERSION=0.10.1a1 PREV_VERSION=0.10.0 bootstrap_envs.sh <scratch-dir> [--enterprise]
#        then: export SB=<scratch-dir>
#
# Venvs (names the agent brief refers to):
#   new     reflex[db]==$NEW_VERSION                        the version under test
#   prev    reflex[db]==$PREV_VERSION                       the previous release (before/after baseline)
#   ctrl-X  reflex[db]==X for each X in $CTRL_VERSIONS      positive controls (versions a finding reproduced on)
#   driver  playwright, httpx, websockets, pip              browser drivers and HTTP probes
#   new-ent / prev-ent  (with --enterprise)                 + reflex-enterprise and oidc-provider-mock
#
# Enterprise: set ENT_WHEEL to a user-supplied offline wheel (bypasses the login gate; never commit it), or
# ENT_SPEC to a PyPI requirement such as 'reflex-enterprise[mcp]==0.9.8' (run enterprise apps with CI=true).
#
# Resolution: a version under test that is a pre-release resolves with --prerelease=allow. A final one (prev, a
# final control) resolves without it, and with every reflex package it requires held to that reflex release's
# PyPI upload time (--exclude-newer-package; reflex uploads last in its train). Otherwise the previous release's
# `>=` sibling floors pick up the new train's alphas or finals, and the baseline silently runs code under test.
# Everything else resolves as a user's install would today. PYDANTIC_PIN (default
# 'pydantic<2.15') keeps the transitive graph user-like. Packages install from wheels only (ONLY_BINARY, default
# ':all:'): uv reuses a cached sdist build for later installs of the same version, so one --no-binary experiment
# would otherwise leak into every venv built after it. Do sdist experiments with their own UV_CACHE_DIR.
#
# Never run uv with a reflex checkout as the working directory: its pyproject's exclude-newer window hides fresh
# packages, and the checkout would shadow the installed package. A venv whose install completed is reused; delete
# it to rebuild. Index variables are cleared, so everything resolves from PyPI.
set -euo pipefail
SB="${1:?usage: NEW_VERSION=... PREV_VERSION=... bootstrap_envs.sh <scratch-dir> [--enterprise]}"; ENT="${2:-}"
unset UV_INDEX UV_INDEX_URL UV_DEFAULT_INDEX UV_EXTRA_INDEX_URL UV_FIND_LINKS
[ -n "${ENT_WHEEL:-}" ] && ENT_WHEEL="$(realpath -m "$ENT_WHEEL")"
: "${NEW_VERSION:?set NEW_VERSION, e.g. 0.10.1a1}"
: "${PREV_VERSION:?set PREV_VERSION, e.g. 0.10.0}"
PY="${PYTHON_VERSION:-3.12}"
PYDANTIC_PIN="${PYDANTIC_PIN:-pydantic<2.15}"
ONLY_BINARY="${ONLY_BINARY-:all:}"
mkdir -p "$SB/envs" "$SB/apps" "$SB/logs" "$SB/downloads"; SB="$(cd "$SB" && pwd -P)"; cd "$SB"

is_pre() { [[ "$1" =~ (a|b|rc|\.dev)[0-9]+ ]]; }

held_siblings() { # reflex version, python: an --exclude-newer-package flag per reflex package it requires
  curl -fsS "https://pypi.org/pypi/reflex/$1/json" | "$2" -I -c 'import json, re, sys
d = json.load(sys.stdin)
cut = max(u["upload_time_iso_8601"] for u in d["urls"])
reqs = [re.match(r"[A-Za-z0-9._-]+", r).group().lower() for r in d["info"]["requires_dist"] or []]
print(" ".join(f"--exclude-newer-package={n}={cut}" for n in sorted({"reflex", *reqs}) if n.startswith("reflex")))'
}

mk() { # name, version-that-decides-resolution, pip args...
  local name="$1" ver="$2" dir="$SB/envs/$1" held; shift 2
  [ -f "$dir/.bootstrap-ok" ] && return 0
  local opts=()
  [ -n "$ONLY_BINARY" ] && opts+=(--only-binary "$ONLY_BINARY")
  uv --no-config venv -q --clear --python "$PY" "$dir"
  if is_pre "$ver"; then
    opts+=(--prerelease=allow)
  elif [ "$ver" != 0 ]; then
    held="$(held_siblings "$ver" "$dir/bin/python")"
    read -ra held_opts <<< "$held"
    opts+=("${held_opts[@]}")
  fi
  uv --no-config pip install -q --python "$dir/bin/python" "${opts[@]}" "$@"
  touch "$dir/.bootstrap-ok"
}
# greenlet must arrive through the db extra: never add it by hand to new/prev.
# The published reflex wheel pins reflex-base to its own version, so reflex[db]==X brings the matching reflex-base.
mk new "$NEW_VERSION" "reflex[db]==$NEW_VERSION" "$PYDANTIC_PIN"
# PREV_EXTRAS adds packages to prev only (e.g. greenlet for a 0.9.x prev, whose db extra predates it).
# shellcheck disable=SC2086
mk prev "$PREV_VERSION" "reflex[db]==$PREV_VERSION" "$PYDANTIC_PIN" ${PREV_EXTRAS:-}
for v in ${CTRL_VERSIONS:-}; do
  # 0.9.x controls need greenlet by hand (SQLAlchemy 2.1 dropped it from its default install).
  mk "ctrl-$v" "$v" "reflex[db]==$v" "$PYDANTIC_PIN" greenlet
done
mk driver 0 playwright httpx websockets pip
[ -x /opt/pw-browsers/chromium ] || "$SB/envs/driver/bin/python" -m playwright install chromium >/dev/null 2>&1 \
  || echo "playwright chromium install failed; set the Chromium path manually"

if [ "$ENT" = "--enterprise" ]; then
  ENT_REQ="${ENT_WHEEL:-${ENT_SPEC:-}}"
  [ -n "$ENT_REQ" ] || { echo "--enterprise needs ENT_WHEEL=<offline wheel path> or ENT_SPEC=<requirement>"; exit 3; }
  case "$ENT_REQ" in *.whl) [ -f "$ENT_REQ" ] || { echo "enterprise wheel missing: $ENT_REQ"; exit 3; }; ENT_REQ="$ENT_REQ[mcp]";; esac
  mk new-ent "$NEW_VERSION" "reflex[db]==$NEW_VERSION" "$PYDANTIC_PIN" "$ENT_REQ" oidc-provider-mock
  # shellcheck disable=SC2086
  mk prev-ent "$PREV_VERSION" "reflex[db]==$PREV_VERSION" "$PYDANTIC_PIN" ${PREV_EXTRAS:-} "$ENT_REQ" oidc-provider-mock
fi

# Print every reflex package per venv: a baseline that resolved a sibling to the version under test shows here.
for e in new prev $(for v in ${CTRL_VERSIONS:-}; do echo "ctrl-$v"; done) new-ent prev-ent; do
  [ -x "$SB/envs/$e/bin/python" ] || continue
  echo "== $e: $(cd "$SB" && "$SB/envs/$e/bin/python" -I -c 'import importlib.metadata as m
names = sorted({d.metadata["Name"].lower() for d in m.distributions()})
keep = [n for n in names if n.startswith("reflex")] + ["sqlalchemy", "greenlet", "pydantic"]
print(" ".join(f"{n}={m.version(n)}" for n in keep if n in names))')"
done
printf 'export SB=%q\n' "$SB"
