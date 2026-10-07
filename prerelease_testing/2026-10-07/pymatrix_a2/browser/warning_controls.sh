#!/bin/sh
# Read-only published-package comparisons from a neutral directory.
set -eu
SB=${1:?scratch root required}
DEST=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
OUTPUT=${2:-"$DEST/warning-controls"}
cd "$SB/apps/pymatrix_a2"
mkdir -p "$OUTPUT"
for envname in stable alpha alpha2; do
  REFLEX_TEST_ENV="$envname" PYTHONWARNINGS=default REFLEX_TELEMETRY_ENABLED=false UV_CACHE_DIR="$SB/uv-cache" uv --no-config run --no-project --python "$SB/envs/$envname/bin/python" python "$DEST/probe.py" > "$OUTPUT/$envname-metadata.json"
  REFLEX_TEST_ENV="$envname" PYTHONWARNINGS=default REFLEX_TELEMETRY_ENABLED=false UV_CACHE_DIR="$SB/uv-cache" uv --no-config run --no-project --python "$SB/envs/$envname/bin/python" python "$DEST/warning_model.py" > "$OUTPUT/$envname.log" 2>&1
done
