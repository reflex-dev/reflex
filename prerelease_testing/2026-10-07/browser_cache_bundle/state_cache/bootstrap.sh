#!/usr/bin/env bash
set -euo pipefail
QA_SCRATCH=${1:?Pass a new neutral scratch directory}
QA_ARTIFACT=$(cd "$(dirname "$0")" && pwd)
for QA_TRAIN in alpha2 alpha stable driver; do
  if [ -e "$QA_SCRATCH/envs/$QA_TRAIN" ]; then
    echo "Refusing to overwrite existing environment $QA_SCRATCH/envs/$QA_TRAIN" >&2
    exit 2
  fi
done
mkdir -p "$QA_SCRATCH"
cd "$QA_SCRATCH"
export UV_CACHE_DIR="$QA_SCRATCH/uv-cache"
for QA_TRAIN in alpha2 alpha stable driver; do
  uv --no-config venv --python 3.12 "$QA_SCRATCH/envs/$QA_TRAIN"
  uv --no-config pip install --python "$QA_SCRATCH/envs/$QA_TRAIN/bin/python" --index-url https://pypi.org/simple --prerelease=allow -r "$QA_ARTIFACT/environment/$QA_TRAIN.txt"
done
uv --no-config run --no-project --python "$QA_SCRATCH/envs/driver/bin/python" python -m playwright install chromium webkit
