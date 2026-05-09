#!/usr/bin/env bash
set -euo pipefail

: "${TAG:?}"
: "${PKG:?}"
: "${VERSION:?}"
: "${GH_TOKEN:?}"
: "${GITHUB_SHA:?}"

gh release create "$TAG" \
  --title "$PKG@$VERSION" \
  --notes "Automated release for $PKG v$VERSION" \
  --target "$GITHUB_SHA" \
  --latest=false
