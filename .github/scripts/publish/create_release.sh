#!/usr/bin/env bash
set -euo pipefail

: "${TAG:?}"
: "${PKG:?}"
: "${VERSION:?}"
: "${PRERELEASE:?}"
: "${MARK_LATEST:?}"
: "${NOTES_PATH:?}"
: "${GH_TOKEN:?}"
: "${GITHUB_SHA:?}"

if gh release view "$TAG" --json name >/dev/null 2>&1; then
  echo "Release $TAG already exists; skipping (safe re-run)."
  exit 0
fi

ARGS=(--title "$PKG@$VERSION" --notes-file "$NOTES_PATH" --target "$GITHUB_SHA")
if [[ "$PRERELEASE" == "true" ]]; then
  ARGS+=(--prerelease --latest=false)
elif [[ "$MARK_LATEST" == "true" ]]; then
  ARGS+=(--latest)
else
  ARGS+=(--latest=false)
fi

gh release create "$TAG" "${ARGS[@]}"
