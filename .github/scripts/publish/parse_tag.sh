#!/usr/bin/env bash
set -euo pipefail

: "${TAG:?}"

# Tag format: v1.2.3 for reflex, reflex-lucide-v0.1.0 for sub-packages
if [[ "$TAG" =~ ^v([0-9].*)$ ]]; then
  PACKAGE="reflex"
  BUILD_DIR="."
  VERSION="${BASH_REMATCH[1]}"
elif [[ "$TAG" =~ ^(.+)-v([0-9].*)$ ]]; then
  PACKAGE="${BASH_REMATCH[1]}"
  VERSION="${BASH_REMATCH[2]}"
  if [ -d "packages/$PACKAGE" ]; then
    BUILD_DIR="packages/$PACKAGE"
  else
    echo "Error: no build directory known for package '$PACKAGE'"
    exit 1
  fi
else
  echo "Error: Tag '$TAG' does not match expected format (v* or <package>-v*)"
  exit 1
fi

{
  echo "package=$PACKAGE"
  echo "build_dir=$BUILD_DIR"
  echo "version=$VERSION"
} >> "$GITHUB_OUTPUT"
