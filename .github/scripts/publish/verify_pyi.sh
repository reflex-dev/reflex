#!/usr/bin/env bash
set -euo pipefail

: "${BUILD_DIR:?}"

if unzip -l "$BUILD_DIR"/dist/*.whl | grep '\.pyi$'; then
  echo "✓ .pyi files found in distribution"
else
  echo "Error: No .pyi files found in wheel"
  exit 1
fi
