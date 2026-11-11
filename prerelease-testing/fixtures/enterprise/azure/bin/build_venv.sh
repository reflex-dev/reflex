#!/usr/bin/env bash
# reflex-azure-auth (generic OIDC on top of reflex-enterprise; its on_load handlers read self.router.url / query params).
# Usage: build_venv.sh [name=compact-enterprise-az] [reflex req=reflex] [enterprise req=reflex-enterprise] [azure req=reflex-azure-auth==0.1.2]
# Pass an offline enterprise wheel path as the 3rd arg to test an unpublished enterprise build.
. "$(dirname "$0")/../../lib.sh"; cd "$SB" || exit 1
N=${1:-compact-enterprise-az}; V=$SB/envs/$N
uv --no-config venv -q --clear --python 3.12 "$V"
uv --no-config pip install -q --python "$V/bin/python" --prerelease=allow "${2:-reflex}" "${3:-reflex-enterprise}" "${4:-reflex-azure-auth==0.1.2}"
uv --no-config pip freeze --python "$V/bin/python" | grep -E '^(reflex|reflex-base|reflex-enterprise|reflex-azure-auth|authlib|pydantic)[ =@]'
