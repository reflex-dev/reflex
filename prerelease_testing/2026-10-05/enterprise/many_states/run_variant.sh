#!/usr/bin/env bash
set -euo pipefail

variant="${1:?Specify alpha or stable}"
state_count="${2:?Specify the dormant state count}"
mode="${3:-prod}"
venv_python="${4:?Specify the isolated environment bin/python}"

case "$variant" in alpha|stable) ;; *) exit 2 ;; esac
case "$mode" in dev|prod) ;; *) exit 2 ;; esac
case "$state_count" in *[!0-9]*|'') exit 2 ;; esac

sample_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$sample_dir/$variant"
backend_port=3133
if [[ "$mode" == dev ]]; then backend_port=8133; fi

exec env -u PYTHONPATH CI=true QA_EXTRA_STATES="$state_count" \
  UV_CACHE_DIR=/private/tmp/reflex-enterprise-uv-cache \
  uv --no-config run --no-project --python "$venv_python" \
  reflex run --env "$mode" --frontend-port 3133 \
  --backend-port "$backend_port" --loglevel debug
