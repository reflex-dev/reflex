#!/usr/bin/env bash
# Build the $ENT_DRV client venv used by the a4auth matrix drivers and the MCP clients (reflex + enterprise[mcp] + playwright;
# pytest because drive_auth.py / recheck_reload.py import the upstream test module).
# Usage: build_ent_drv.sh [reflex-enterprise requirement=reflex-enterprise[mcp]] [reflex requirement=reflex]
# Pass a wheel path for an offline enterprise build, e.g. build_ent_drv.sh "/path/reflex_enterprise-X-py3-none-any.whl[mcp]".
. "$(dirname "$0")/../../lib.sh"
cd "$SB" || exit 1
uv --no-config venv -q --clear --python 3.12 "$SB/envs/$ENT_DRV"
uv --no-config pip install -q --python "$SB/envs/$ENT_DRV/bin/python" --prerelease=allow "${2:-reflex}" "${1:-reflex-enterprise[mcp]}" playwright==1.63.0 httpx pytest
uv --no-config pip freeze --python "$SB/envs/$ENT_DRV/bin/python" | grep -E '^(reflex|reflex-base|reflex-enterprise|mcp|playwright)[ =@]'
