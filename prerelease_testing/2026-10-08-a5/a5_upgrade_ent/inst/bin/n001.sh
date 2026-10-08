#!/usr/bin/env bash
# N-001 / F-005 / F-006 / F-014 on reflex 0.10.0a5: fresh venvs, NOTHING added by hand, no --pre / no --prerelease flag
# uv: --prerelease=allow (without it uv refuses: pre-existing uv semantics, see logs/install-uv311-noflag.log); pip: no --pre (an exact ==0.10.0a5 pin is explicit).
# Venvs: $SB/envs/a5_upgrade_ent-n001-{uv311,uv314,pip311,pip314} = 'reflex[db]==0.10.0a5'; -f006pip312 = plain 'reflex==0.10.0a5'.
set -u
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a5_upgrade_ent/inst; L=$W/logs
cd $SB
pkgs() { $1/bin/python -I -c "
import importlib.metadata as m
def g(p):
    try: return m.version(p)
    except Exception: return 'NOT-INSTALLED'
print(' '.join(p+'='+g(p) for p in ['reflex','reflex-base','sqlalchemy','sqlmodel','greenlet','alembic','pydantic','reflex-components-core','reflex-components-radix','reflex-hosting-cli','reflex-build-sdk']))"; }
for spec in ${SPECS:-uv311:uv:3.11:db uv314:uv:3.14:db pip311:pip:3.11:db pip314:pip:3.14:db f006pip312:pip:3.12:plain}; do
  IFS=: read k tool py kind <<< "$spec"; V=$SB/envs/a5_upgrade_ent-n001-$k; rm -rf $V
  req='reflex[db]==0.10.0a5'; [ $kind = plain ] && req='reflex==0.10.0a5'
  if [ $tool = uv ]; then
    uv --no-config venv -q --python $py $V 2>&1 | grep -v UV_NATIVE
    uv --no-config pip install --python $V/bin/python ${UVFLAG:---prerelease=allow} "$req" > $L/install-$k.log 2>&1; rc=$?
  else
    uv --no-config venv -q --seed --python $py $V 2>&1 | grep -v UV_NATIVE
    $V/bin/python -m pip install --disable-pip-version-check "$req" > $L/install-$k.log 2>&1; rc=$?
  fi
  $V/bin/python -m pip freeze 2>/dev/null > $L/freeze-$k.txt || uv --no-config pip freeze --python $V/bin/python > $L/freeze-$k.txt 2>/dev/null
  echo "py$py/$tool '$req' rc=$rc: $(pkgs $V)"
  echo "  pre-releases in graph: $(grep -E '(a|b|rc)[0-9]+$|\.dev' $L/freeze-$k.txt | tr '\n' ' ')"
  $V/bin/python -I -c "import reflex.model; print('  import reflex.model OK')" 2>&1 | tail -1
  if [ $tool = pip ]; then (cd $SB && $V/bin/python -m pip check 2>&1 | tail -1 | sed 's/^/  pip check: /'); else (cd $SB && uv --no-config pip check --python $V/bin/python 2>&1 | grep -v UV_NATIVE | tail -1 | sed 's/^/  uv pip check: /'); fi
done
