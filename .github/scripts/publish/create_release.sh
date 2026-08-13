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

# The root package is the repository, so its tag (v1.2.3) already names the
# release unambiguously; only a sub-package needs to say which package it is.
TITLE="$PKG@$VERSION"
if [[ "$PKG" == "reflex" ]]; then
  TITLE="$TAG"
fi

ARGS=(--title "$TITLE" --notes-file "$NOTES_PATH" --target "$GITHUB_SHA")
if [[ "$PRERELEASE" == "true" ]]; then
  ARGS+=(--prerelease --latest=false)
elif [[ "$MARK_LATEST" == "true" ]]; then
  ARGS+=(--latest)
else
  ARGS+=(--latest=false)
fi

gh release create "$TAG" "${ARGS[@]}"
