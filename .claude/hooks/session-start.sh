#!/bin/bash
# SessionStart hook for Claude Code on the web.
#
# The web container image is baked with tools that predate this repo's current
# requirements, so a fresh `uv sync` + test run fails out of the box. This hook
# reconciles the environment with the repo on every web session start:
#
#   1. uv: the repo pins tool.uv.required-version in pyproject.toml. The web
#      image usually already has a compatible uv installed (e.g. in
#      /usr/local/bin), but an older standalone build can sit ahead of it on
#      PATH. We pick whichever installed uv meets the requirement and put it
#      first; only if none qualifies do we install one from PyPI (the astral.sh
#      installer and `uv self update` are blocked / GitHub-rate-limited here).
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

# 1. Put a uv satisfying the repo's required-version in ~/.local/bin and front-load
#    that dir, leaving the system PATH order untouched. Symlink a compatible uv if
#    one exists elsewhere; only pip-install when none is found.
local_bin="$HOME/.local/bin"
req="$(sed -n 's/^[[:space:]]*required-version[[:space:]]*=[[:space:]]*"[^0-9]*\([0-9][0-9.]*\).*/\1/p' pyproject.toml | head -n1)"

uv_satisfies() {  # $1=uv binary; true if its version >= $req (or no req parsed)
  local v
  v="$("$1" --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -n1)"
  [ -n "$v" ] || return 1
  [ -z "$req" ] && return 0
  [ "$(printf '%s\n%s\n' "$req" "$v" | sort -V | head -n1)" = "$req" ]
}

# Front-load ~/.local/bin here and -- via CLAUDE_ENV_FILE -- for later commands.
export PATH="$local_bin:$PATH"
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$CLAUDE_ENV_FILE"
fi

if ! uv_satisfies "$local_bin/uv"; then
  mkdir -p "$local_bin"
  for cand in $(type -aP uv 2>/dev/null) /usr/local/bin/uv /usr/bin/uv; do
    uv_satisfies "$cand" && ln -sf "$cand" "$local_bin/uv" && break
  done
  uv_satisfies "$local_bin/uv" ||
    python3 -m pip install --user --quiet --root-user-action=ignore "uv${req:+>=$req}"
fi
hash -r 2>/dev/null || true

# 2. Ensure a stable interpreter matching .python-version is installed, so sync
#    doesn't fall back to the pre-baked prerelease.
uv python install

# 3. Fetch tags so the dynamic version resolves (ignore failures; offline runs
#    still get a best-effort sync).
git fetch --tags --quiet || true

# 4. Install all workspace dependencies (uses .python-version). Don't let a
#    transient sync failure (e.g. a flaky network) abort startup -- the container
#    should still come up so the session can retry sync manually.
if ! uv sync; then
  echo "WARNING: 'uv sync' failed; the environment may be incomplete. Re-run 'uv sync' once any transient issue clears." >&2
fi

echo "Environment ready: uv $(uv --version), Python $(uv run python --version 2>/dev/null), reflex $(uv run python -c 'import importlib.metadata as m; print(m.version("reflex"))' 2>/dev/null || echo '?')"
