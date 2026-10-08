#!/usr/bin/env bash
# Baseline venvs for the a5 in-place upgrades (same specs as the a4 pass):
#  fd / twr = what a 0.9.12 user has: -r requirements.txt 'reflex==0.9.12' (+ 'sqlalchemy<2.1' for these db apps, as the a3/a4 passes);
#  twa4     = what an a4 tester has: -r requirements.txt 'reflex[db]==0.10.0a4' 'pydantic<2.14' (--prerelease=allow).
set -u
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a5_upgrade_ent/up; cd $SB
for spec in ${@:-fd:form-designer:db twr:twitter-redis:db twa4:twitter-redis:a4}; do
  k=${spec%%:*}; rest=${spec#*:}; app=${rest%%:*}; db=${rest##*:}
  V=$SB/envs/a5_upgrade_ent-$k; rm -rf $V
  uv --no-config venv -q --python 3.12 $V 2>&1 | grep -v UV_NATIVE
  if [ "$db" = a4 ]; then
    uv --no-config pip install -q --python $V/bin/python --prerelease=allow -r $W/$app/requirements.txt 'reflex[db]==0.10.0a4' 'pydantic<2.14' 2>&1 | grep -v UV_NATIVE
  else
    extra=(); [ "$db" = db ] && extra=('sqlalchemy<2.1')
    uv --no-config pip install -q --python $V/bin/python -r $W/$app/requirements.txt 'reflex==0.9.12' "${extra[@]}" 2>&1 | grep -v UV_NATIVE
  fi
  uv --no-config pip freeze --python $V/bin/python 2>/dev/null > $W/freeze/$k-base.txt
  echo "$k ($app): $(grep -E '^(reflex|reflex-base|sqlalchemy|greenlet|sqlmodel|pydantic|reflex-local-auth)==' $W/freeze/$k-base.txt | tr '\n' ' ')"
done
