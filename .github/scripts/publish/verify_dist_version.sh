#!/usr/bin/env bash
set -euo pipefail

: "${VERSION:?}"

# Every built artifact must carry the target version in its filename
# (<name>-<version>-....whl / <name>-<version>.tar.gz). Catches a
# misconfigured uv-dynamic-versioning tag prefix producing e.g. 0.0.0dev0.
shopt -s nullglob
FILES=(dist/*)
if [[ ${#FILES[@]} -eq 0 ]]; then
  echo "Error: no artifacts in dist/"
  exit 1
fi
for f in "${FILES[@]}"; do
  base=$(basename "$f")
  if [[ "$base" != *"-${VERSION}-"* && "$base" != *"-${VERSION}.tar.gz" ]]; then
    echo "Error: artifact '$base' does not match target version ${VERSION}"
    exit 1
  fi
done
echo "✓ ${#FILES[@]} artifact(s) at version ${VERSION}"
