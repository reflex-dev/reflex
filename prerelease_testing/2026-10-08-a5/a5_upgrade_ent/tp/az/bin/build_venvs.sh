#!/usr/bin/env bash
# reflex-azure-auth 0.1.2 (generic OIDC on top of reflex-enterprise; on_load handlers read self.router.url / query_parameters)
# on a5 and a4: py3.12, reflex+reflex-base pinned, pydantic<2.14, the OFFLINE enterprise 0.9.7a5 wheel by file path.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; T=$SB/apps/a5_upgrade_ent/tp; cd $SB
WHL=$SB/downloads/enterprise_wheel_a5/reflex_enterprise-0.9.7a5-0offline-py3-none-any.whl
for spec in az:0.10.0a5 az4:0.10.0a4; do
  k=${spec%%:*}; ver=${spec#*:}; V=$SB/envs/a5_upgrade_ent-$k
  uv --no-config venv -q --clear --python 3.12 $V 2>&1 | grep -v UV_NATIVE
  uv --no-config pip install -q --python $V/bin/python --prerelease=allow "reflex==$ver" "reflex-base==$ver" 'pydantic<2.14' 'reflex-azure-auth==0.1.2' "$WHL" 2>&1 | grep -v UV_NATIVE
  uv --no-config pip freeze --python $V/bin/python 2>/dev/null > $T/logs/az-$k-freeze.txt
  echo "$k: $(grep -E '^(reflex|reflex-base|reflex-enterprise|reflex-azure-auth|authlib|pydantic)( @|==)' $T/logs/az-$k-freeze.txt | sed 's# @ file.*#@offline-wheel#' | tr '\n' ' ')"
done
