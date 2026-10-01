#!/bin/bash
# SessionStart hook for Claude Code on the web.
#
# The web container image is baked with tools that predate this repo's current
# requirements, so a later `uv sync` + test run fails out of the box. This hook
# reconciles the environment with the repo on every web session start (it does
# not sync dependencies -- that cost is paid on the first 'uv run'/'uv sync'):
#
#   1. uv: the repo pins tool.uv.required-version in pyproject.toml. If the uv on
#      PATH is older, pip-install a satisfying one for --user (into ~/.local/bin,
#      assumed already on PATH); the astral.sh installer and `uv self update` are
#      blocked / GitHub-rate-limited here.
#   2. Python: an older uv (see #1) predates Python 3.14.0 final, so its bundled
#      release manifest only knows 3.14 prereleases -- a bare `uv sync` with it
#      resolves .python-version=3.14 to a release candidate whose
#      typing._eval_type signature is incompatible with the pinned pydantic
#      (breaks every import). Upgrading uv first fixes the manifest; we then run
#      `uv python install` (which excludes prereleases) as a guard so a later
#      sync can't reuse a prerelease that an earlier stale-uv run may have
#      already fetched.
#   3. git tags: web clones are shallow with no tags, so Reflex's VCS-derived
#      version resolves to 0.0.0 and trips downstream version gates (e.g.
#      reflex-hosting-cli rejects it). Fetching tags lets the version compute.
set -euo pipefail

# Only the web container needs this fixup; local dev environments are managed
# by the developer.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

# 1. Ensure the uv on PATH satisfies the repo's required-version; if not, pip
#    installs a satisfying one into ~/.local/bin (assumed already on PATH).
req="$(sed -n 's/^[[:space:]]*required-version[[:space:]]*=[[:space:]]*"[^0-9]*\([0-9][0-9.]*\).*/\1/p' pyproject.toml | head -n1)"

uv_satisfies() {  # $1=uv binary; true if its version >= $req (or no req parsed)
  local v
  v="$("$1" --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -n1)"
  [ -n "$v" ] || return 1
  [ -z "$req" ] && return 0
  [ "$(printf '%s\n%s\n' "$req" "$v" | sort -V | head -n1)" = "$req" ]
}

if ! uv_satisfies uv; then
  python3 -m pip install --user --quiet --root-user-action=ignore "uv${req:+>=$req}"
  hash -r 2>/dev/null || true
fi

# 2. Ensure a stable interpreter matching .python-version is installed, so sync
#    doesn't fall back to the pre-baked prerelease.
uv python install

# 3. Fetch tags so the dynamic version resolves (ignore failures; offline runs
#    still compute a best-effort version).
git fetch --tags --quiet || true

# Dependencies are intentionally not synced here -- the first 'uv run'/'uv sync'
# (e.g. running tests or an app) installs them, so sessions that don't touch the
# code don't pay that cost.
echo "Environment ready: uv $(uv --version). Dependencies install on first 'uv sync' / 'uv run'."
