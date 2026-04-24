#!/usr/bin/env bash
set -euo pipefail

: "${TAG:?}"
: "${PKG:?}"
: "${VERSION:?}"
: "${ACTION:?}"
: "${GH_TOKEN:?}"
: "${GITHUB_SHA:?}"

ARGS=(--title "$PKG@$VERSION" --notes "Dispatch release for $PKG v$VERSION (action=$ACTION)" --target "$GITHUB_SHA")
if [[ "$ACTION" == release-* ]]; then
  if [[ "$PKG" != "reflex" ]]; then
    ARGS+=(--latest=false)
  fi
else
  ARGS+=(--prerelease --latest=false)
fi

gh release create "$TAG" "${ARGS[@]}"
