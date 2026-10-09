#!/usr/bin/env bash
# reflex-azure-auth 0.1.2 (generic OIDC on top of reflex-enterprise; its on_load handlers read self.router.url / query_parameters).
# Usage: build_venvs.sh [key:reflex-version ...]  (default "az:$NEW_VERSION") -> $SB/envs/$VENV_PREFIX-<key>
# reflex-enterprise comes from PyPI (ENT_SPEC, default 'reflex-enterprise==0.9.7') or from a local wheel (ENT_WHEEL=/path/to.whl,
# e.g. an offline pre-release wheel; never commit it). AZ_EXTRA for extra pins (the 0.10 alphas needed 'pydantic<2.14').
set -u; . "$(dirname "$0")/../../../bin/env.sh"; T=$(cd "$(dirname "$0")/.." && pwd); mkdir -p "$T/logs"
ENT=${ENT_WHEEL:-${ENT_SPEC:-reflex-enterprise==0.9.7}}
for spec in ${@:-az:$NEW_VERSION}; do
  k=${spec%%:*}; ver=${spec#*:}; V=$SB/envs/$VENV_PREFIX-$k
  uvq venv -q --clear --python ${PY:-3.12} "$V"
  uvq pip install -q --python "$V/bin/python" $(pre_flag "$ver") "reflex==$ver" "reflex-base==$ver" ${AZ_EXTRA:-} 'reflex-azure-auth==0.1.2' "$ENT"
  uvq pip freeze --python "$V/bin/python" > "$T/logs/az-$k-freeze.txt"
  echo "$k: $(grep -E '^(reflex|reflex-base|reflex-enterprise|reflex-azure-auth|authlib|pydantic)( @|==)' "$T/logs/az-$k-freeze.txt" | sed 's# @ file.*#@local-wheel#' | tr '\n' ' ')"
done
