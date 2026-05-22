#!/usr/bin/env bash
set -euo pipefail

: "${TAG:?}"

# Tag format: v1.2.3 for reflex, reflex-lucide-v0.1.0 for sub-packages.
# Package and version are restricted to a safe character set so the captured
# groups can be interpolated into shell and written to $GITHUB_OUTPUT without
# escaping concerns (a tag can in principle come from any actor able to
# publish a release).
PKG_RE='[A-Za-z0-9_-]+'
VER_RE='[0-9][A-Za-z0-9.+-]*'
if [[ "$TAG" =~ ^v(${VER_RE})$ ]]; then
  PACKAGE="reflex"
  BUILD_DIR="."
  VERSION="${BASH_REMATCH[1]}"
elif [[ "$TAG" =~ ^(${PKG_RE})-v(${VER_RE})$ ]]; then
  PACKAGE="${BASH_REMATCH[1]}"
  VERSION="${BASH_REMATCH[2]}"
  if [ -d "packages/$PACKAGE" ]; then
    BUILD_DIR="packages/$PACKAGE"
  else
    echo "Error: no build directory known for package '$PACKAGE'"
    exit 1
  fi
else
  echo "Error: Tag '$TAG' does not match expected format (v<version> or <package>-v<version>)"
  exit 1
fi

{
  echo "package=$PACKAGE"
  echo "build_dir=$BUILD_DIR"
  echo "version=$VERSION"
} >> "$GITHUB_OUTPUT"
