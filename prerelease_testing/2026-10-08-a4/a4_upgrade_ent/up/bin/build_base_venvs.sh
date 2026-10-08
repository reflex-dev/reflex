#!/usr/bin/env bash
# 0.9.12 baselines resolved like a stable user (no prerelease flag); db apps pinned sqlalchemy<2.1 (a 0.9.12 install from
# before SQLAlchemy 2.1, which still brought greenlet), exactly as the a3 pass (a3_upgrade/bin/build_base_venvs.sh).
# twa3 = what an a3 tester had: reflex[db]==0.10.0a3 (+pydantic<2.14), for the a3 -> a4 in-place upgrade.
set -u
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a4_upgrade_ent/up; cd $SB
for spec in fd:form-designer:db gh:github-stats: twr:twitter-redis:db twa3:twitter-redis:a3; do
  k=${spec%%:*}; rest=${spec#*:}; app=${rest%%:*}; db=${rest##*:}
  V=$SB/envs/a4_upgrade_ent-$k; rm -rf $V
  uv --no-config venv -q --python 3.12 $V 2>&1 | grep -v UV_NATIVE
  if [ "$db" = a3 ]; then
    uv --no-config pip install -q --python $V/bin/python --prerelease=allow -r $W/$app/requirements.txt 'reflex[db]==0.10.0a3' 'pydantic<2.14' 2>&1 | grep -v UV_NATIVE
  else
    extra=(); [ "$db" = db ] && extra=('sqlalchemy<2.1')
    uv --no-config pip install -q --python $V/bin/python -r $W/$app/requirements.txt 'reflex==0.9.12' "${extra[@]}" 2>&1 | grep -v UV_NATIVE
  fi
  uv --no-config pip freeze --python $V/bin/python 2>/dev/null > $W/freeze/$k-base.txt
  echo "$k ($app): $(grep -E '^(reflex|reflex-base|sqlalchemy|greenlet|sqlmodel|pydantic|reflex-local-auth)==' $W/freeze/$k-base.txt | tr '\n' ' ')"
done
