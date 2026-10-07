#!/usr/bin/env bash
set -euo pipefail
SB=${REFLEX_TEST_SB:?Set a new neutral scratch root}
ARTIFACT=$(cd "$(dirname "$0")/.." && pwd)
for NAME in forms-alpha2 forms-alpha forms-stable driver; do
  if [ -e "$SB/envs/$NAME" ]; then echo "Refusing existing env $NAME" >&2; exit 2; fi
done
mkdir -p "$SB/envs" "$SB/apps/browser-bundle"
cd "$SB"
export UV_CACHE_DIR="$SB/uv-cache"
for TRAIN in alpha2 alpha stable; do
  uv --no-config venv --python 3.12 "$SB/envs/forms-$TRAIN"
  uv --no-config pip install --python "$SB/envs/forms-$TRAIN/bin/python" --prerelease=allow --index-url https://pypi.org/simple -r "$ARTIFACT/logs/$TRAIN-freeze.txt"
done
uv --no-config venv --python 3.12 "$SB/envs/driver"
uv --no-config pip install --python "$SB/envs/driver/bin/python" --index-url https://pypi.org/simple -r "$ARTIFACT/logs/driver-freeze.txt"
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python -m playwright install chromium webkit
cp -R "$ARTIFACT/source" "$ARTIFACT/scripts" "$SB/apps/browser-bundle/"
mkdir -p "$SB/apps/browser-bundle/logs"
