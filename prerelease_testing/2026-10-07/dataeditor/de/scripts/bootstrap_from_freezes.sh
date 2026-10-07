#!/usr/bin/env bash
set -euo pipefail
SB=${REFLEX_TEST_SB:?Set REFLEX_TEST_SB to a new neutral scratch directory}
ARTIFACT=$(cd "$(dirname "$0")/.." && pwd)
for TRAIN in alpha2 alpha stable driver; do
  if [ -e "$SB/envs/$TRAIN" ]; then
    echo "Refusing to modify existing environment $SB/envs/$TRAIN" >&2
    exit 2
  fi
done
mkdir -p "$SB/envs" "$SB/apps/dataeditor"
cd "$SB"
export UV_CACHE_DIR="$SB/uv-cache"
for TRAIN in alpha2 alpha stable driver; do
  uv --no-config venv --python 3.12 "$SB/envs/$TRAIN"
  uv --no-config pip install --python "$SB/envs/$TRAIN/bin/python" --prerelease=allow --index-url https://pypi.org/simple -r "$ARTIFACT/logs/$TRAIN-freeze.txt"
done
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python -m playwright install chromium
cp -R "$ARTIFACT/source" "$SB/apps/dataeditor/source"
cp -R "$ARTIFACT/scripts" "$SB/apps/dataeditor/scripts"
mkdir -p "$SB/apps/dataeditor/logs"
