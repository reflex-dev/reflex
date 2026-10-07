#!/bin/sh
# Install published packages only, from neutral scratch.
set -eu
SB=${1:?scratch root required}
DEST=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
OUTPUT=${2:-"$DEST/environment"}
mkdir -p "$SB/apps/tooling_otel" "$OUTPUT"
cd "$SB/apps/tooling_otel"
export UV_CACHE_DIR="$SB/uv-cache"
export UV_PYTHON_INSTALL_DIR="$SB/uv-python"
target="$SB/envs/otel-a2"
test ! -e "$target" || { echo "Refusing existing environment: $target"; exit 1; }
uv --no-config venv --python 3.11.16 "$target" > "$OUTPUT/install.log" 2>&1
uv --no-config pip install --python "$target/bin/python" --prerelease=allow -r "$DEST/environment/alpha2.txt" >> "$OUTPUT/install.log" 2>&1
uv --no-config pip freeze --python "$target/bin/python" > "$OUTPUT/alpha2.txt"
