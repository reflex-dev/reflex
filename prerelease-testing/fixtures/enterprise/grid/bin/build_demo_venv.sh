#!/usr/bin/env bash
# Venv for the AG Grid demo (needs faker/pandas/aiosqlite on top of reflex[db] + reflex-enterprise[mcp]).
# Usage: build_demo_venv.sh <name> [reflex req=reflex[db]] [enterprise req=reflex-enterprise[mcp]]   -> $SB/envs/<name>
. "$(dirname "$0")/../../lib.sh"; cd "$SB" || exit 1
N=$1; uv --no-config venv -q --clear --python 3.12 "$SB/envs/$N"
uv --no-config pip install -q --python "$SB/envs/$N/bin/python" --prerelease=allow "${2:-reflex[db]}" "${3:-reflex-enterprise[mcp]}" faker==36.2.2 pandas==2.2.3 aiosqlite
uv --no-config pip freeze --python "$SB/envs/$N/bin/python" | grep -E '^(reflex|reflex-base|reflex-enterprise|sqlalchemy|greenlet|pydantic)[ =@]'
