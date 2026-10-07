#!/usr/bin/env bash
# 0.9.12 baselines resolved like a stable user (no prerelease flag); db apps pinned sqlalchemy<2.1 (a 0.9.12 install from before
# SQLAlchemy 2.1, which still brought greenlet), as in the a2 pass.
set -u
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a3_upgrade; cd $SB
for spec in fd:form-designer:db gh:github-stats: ck:clock: tw:twitter:db twr:twitter-redis:db; do
  k=${spec%%:*}; rest=${spec#*:}; app=${rest%%:*}; db=${rest##*:}
  V=$SB/envs/a3_upgrade-$k; rm -rf $V
  uv --no-config venv -q --python 3.12 $V 2>&1 | grep -v UV_NATIVE
  extra=(); [ "$db" = db ] && extra=('sqlalchemy<2.1')
  uv --no-config pip install -q --python $V/bin/python -r $W/$app/requirements.txt 'reflex==0.9.12' "${extra[@]}" 2>&1 | grep -v UV_NATIVE
  uv --no-config pip freeze --python $V/bin/python 2>/dev/null > $W/freeze/$k-base.txt
  echo "$k ($app): $(grep -E '^(reflex|reflex-base|sqlalchemy|greenlet|sqlmodel|pydantic|reflex-local-auth)==' $W/freeze/$k-base.txt | tr '\n' ' ')"
done
