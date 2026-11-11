#!/usr/bin/env bash
# builds the extra venvs for the enterprise item (run with cwd=$SB, --no-config)
SB=${SB:?}; cd "$SB" || exit 1
b() { local n=$1; shift; echo "## $n $(date +%T)"; uv --no-config venv -q --clear --python 3.12 "$SB/envs/$n" && uv --no-config pip install -q --python "$SB/envs/$n/bin/python" --prerelease=allow "$@" && uv --no-config pip freeze --python "$SB/envs/$n/bin/python" | grep -E '^(reflex|reflex-base|reflex-enterprise|mcp|playwright|pydantic|faker)[ =@]'; echo "## $n exit=$? $(date +%T)"; }
b enterprise-drv 'reflex==0.10.1a1' 'reflex-enterprise[mcp]==0.9.8' playwright==1.63.0 httpx pytest 'pydantic<2.15'
b enterprise-ctrl-a3 'reflex[db]==0.10.0a3' 'reflex-enterprise[mcp]==0.9.8' oidc-provider-mock 'pydantic<2.15'
b enterprise-ctrl-rxe96 'reflex[db]==0.10.0' 'reflex-enterprise[mcp]==0.9.6' 'pydantic<2.15'
b enterprise-demo-new 'reflex[db]==0.10.1a1' 'reflex-enterprise[mcp]==0.9.8' faker==36.2.2 pandas==2.2.3 aiosqlite 'pydantic<2.15'
echo ALL_DONE
