#!/usr/bin/env bash
set -euo pipefail

: "${PKG:?}"

LATEST=$(git tag -l "${PKG}-v*" | sed "s/^${PKG}-v//" | sort -V | tail -1)
if [ -z "$LATEST" ]; then
  NEXT="0.0.1"
else
  IFS='.' read -r MAJOR MINOR PATCH <<< "$LATEST"
  NEXT="${MAJOR}.${MINOR}.$((PATCH + 1))"
fi

echo "version=$NEXT" >> "$GITHUB_OUTPUT"
echo "tag=${PKG}-v${NEXT}" >> "$GITHUB_OUTPUT"
