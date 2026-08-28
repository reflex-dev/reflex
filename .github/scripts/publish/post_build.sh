#!/usr/bin/env bash
# Repository-specific artifact checks, run by publish.yml's collect job after
# every build and before the approval gate. PACKAGE, VERSION, BUILD_DIR and
# DIST_DIR are in the environment.
set -euo pipefail

: "${PACKAGE:?}"
: "${DIST_DIR:?}"

# The reflex wheel carries the generated .pyi stubs (scripts/hatch_build.py).
# A build that silently produced none would ship a release with no type
# information, so it must not reach the approver.
if [ "$PACKAGE" = "reflex" ]; then
  if unzip -l "$DIST_DIR"/*.whl | grep '\.pyi$'; then
    echo "✓ .pyi files found in distribution"
  else
    echo "Error: No .pyi files found in wheel"
    exit 1
  fi
fi
