#!/usr/bin/env bash
# Repository-specific artifact checks, run by publish.yml's collect job after
# every build and before the approval gate. PACKAGE, VERSION, BUILD_DIR and
# DIST_DIR are in the environment.
set -euo pipefail

: "${PACKAGE:?}"
: "${BUILD_DIR:?}"
: "${DIST_DIR:?}"

# Every package whose build generates .pyi stubs — reflex itself and the
# component packages alike — must ship them, or the release carries no type
# information. Which packages those are is derived from the package being built,
# not listed anywhere: see scripts/verify_pyi.py.
#
# Located relative to this hook rather than to the working directory, which is
# what DIST_DIR is relative to.
exec uv run --no-config --script \
  "$(dirname "$0")/../../../scripts/verify_pyi.py"
