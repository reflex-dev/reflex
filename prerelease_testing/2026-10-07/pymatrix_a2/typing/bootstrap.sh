#!/usr/bin/env bash
set -euo pipefail

QA_ARTIFACT="$(cd "$(dirname "$0")" && pwd)"
QA_SCRATCH="${1:?Pass a new neutral scratch directory}"
mkdir -p "$QA_SCRATCH"
cd "$QA_SCRATCH"
export UV_CACHE_DIR="$QA_SCRATCH/uv-cache"

uv --no-config venv --python 3.12.14 "$QA_SCRATCH/envs/driver"
uv --no-config venv --python 3.12.14 "$QA_SCRATCH/envs/pymatrix-tools"
uv --no-config pip install --python "$QA_SCRATCH/envs/pymatrix-tools/bin/python" -r "$QA_ARTIFACT/results/final/tools-freeze.txt"

for QA_SPEC in pymatrix-stable-311:3.11.16 pymatrix-a2-311:3.11.16 pymatrix-a2-313:3.13.15 pymatrix-stable-3147:3.14.7 pymatrix-a1-3147:3.14.7 pymatrix-a2-314:3.14.7; do
  QA_NAME="${QA_SPEC%:*}"
  QA_PYTHON="${QA_SPEC#*:}"
  uv --no-config venv --python "$QA_PYTHON" "$QA_SCRATCH/envs/$QA_NAME"
  uv --no-config pip install --python "$QA_SCRATCH/envs/$QA_NAME/bin/python" --prerelease=allow -r "$QA_ARTIFACT/results/final/$QA_NAME-freeze.txt"
done
