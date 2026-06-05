#!/bin/bash
# SessionStart hook for Claude Code on the web.
#
# The web container image is baked with tools that predate this repo's current
# requirements, so a fresh `uv sync` + test run fails out of the box. This hook
# reconciles the environment with the repo on every web session start:
#
#   1. uv: the image ships an older uv than tool.uv.required-version in
#      pyproject.toml. The astral.sh installer and `uv self update` are
#      blocked / GitHub-rate-limited here, so we upgrade from PyPI instead.
#   2. Python: the baked uv (see #1) predates Python 3.14.0 final, so its
#      bundled release manifest only knows 3.14 prereleases -- a bare `uv sync`
#      with it resolves .python-version=3.14 to a release candidate whose
#      typing._eval_type signature is incompatible with the pinned pydantic
#      (breaks every import). Upgrading uv first fixes the manifest; we then run
#      `uv python install` (which excludes prereleases) as a guard so sync can't
#      reuse a prerelease that an earlier stale-uv sync may have already fetched.
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

# 1. Ensure uv meets the repo's required-version. pip is a near-instant no-op
#    when the constraint is already satisfied, and installs from PyPI otherwise
#    (the astral.sh installer and `uv self update` are blocked here).
req="$(sed -n 's/^[[:space:]]*required-version[[:space:]]*=[[:space:]]*"[^0-9]*\([0-9][0-9.]*\).*/\1/p' pyproject.toml | head -n1)"
python3 -m pip install --user --quiet --root-user-action=ignore "uv${req:+>=$req}"

# pip --user installs land in ~/.local/bin; make sure they win over the baked uv.
export PATH="$HOME/.local/bin:$PATH"
hash -r 2>/dev/null || true

# 2. Ensure a stable interpreter matching .python-version is installed, so sync
#    doesn't fall back to the pre-baked prerelease.
uv python install

# 3. Fetch tags so the dynamic version resolves (ignore failures; offline runs
#    still get a best-effort sync).
git fetch --tags --quiet || true

# 4. Install all workspace dependencies (uses .python-version).
uv sync

echo "Environment ready: uv $(uv --version), Python $(uv run python --version 2>/dev/null), reflex $(uv run python -c 'import importlib.metadata as m; print(m.version("reflex"))' 2>/dev/null || echo '?')"
