#!/usr/bin/env bash
set -euo pipefail
SESSION_DEMO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SESSION_REPO_ROOT=$(git -C "$SESSION_DEMO_DIR" rev-parse --show-toplevel)
SESSION_XY_ROOT=${SESSION_XY_ROOT:-/workspace/xy-integration}
export UV_PROJECT_ENVIRONMENT=${SESSION_VENV:-/workspace/reflex/.venv}
export UV_CACHE_DIR=${UV_CACHE_DIR:-/tmp/customization-uv-cache}
export REFLEX_DIR=${REFLEX_DIR:-/workspace/.local/reflex}
export npm_config_cache=${npm_config_cache:-/tmp/customization-npm-cache}
export PYTHONPATH="$SESSION_XY_ROOT/python:$SESSION_REPO_ROOT/packages/reflex-components-internal/src:$SESSION_DEMO_DIR${PYTHONPATH:+:$PYTHONPATH}"
cd "$SESSION_DEMO_DIR"
exec uv run --no-sync reflex "${@:-run}"
