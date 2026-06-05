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
#   2. Python: the image pre-installs a 3.14 prerelease whose typing._eval_type
#      signature is incompatible with the pinned pydantic (breaks every import).
#      `uv sync` would reuse that prerelease since it's the only installed match
#      for .python-version. `uv python install` excludes prereleases, so it
#      fetches the stable patch; once present, sync prefers it over the rc.
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

# 1. Upgrade uv if it's below the repo's required-version.
need_uv="$(python3 - <<'PY'
import re, shutil, subprocess
from pathlib import Path

req = "0"
m = re.search(r'required-version\s*=\s*"[><=~ ]*([0-9][0-9.]*)"', Path("pyproject.toml").read_text())
if m:
    req = m.group(1)

cur = "0"
if shutil.which("uv"):
    out = subprocess.run(["uv", "--version"], capture_output=True, text=True).stdout
    mm = re.search(r"(\d+\.\d+\.\d+)", out)
    if mm:
        cur = mm.group(1)

def tup(v):
    return tuple(int(x) for x in v.split("."))

print("yes" if tup(cur) < tup(req) else "no")
PY
)"

if [ "$need_uv" = "yes" ]; then
  echo "Upgrading uv to satisfy required-version..."
  python3 -m pip install --user --upgrade --quiet uv
fi

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
