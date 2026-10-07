#!/bin/bash
# Build own a3-based venvs (PyPI only): pytest/pytest-mock on 3.12 (a3_class_state-a3) and 3.11/3.13/3.14.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a3_class_state
mkdir -p $W/logs/venv; cd $SB || exit 1
for spec in a3:3.12 a3-py311:3.11 a3-py313:3.13 a3-py314:3.14; do n=${spec%%:*}; py=${spec#*:}
  ( uv --no-config venv --python $py $SB/envs/a3_class_state-$n &&
    uv --no-config pip install --python $SB/envs/a3_class_state-$n/bin/python --prerelease=allow \
      'reflex[db]==0.10.0a3' 'reflex-base==0.10.0a3' 'pydantic<2.14' pytest pytest-mock ) > $W/logs/venv/build-$n.log 2>&1
  echo "$n rc=$?"
  uv --no-config pip freeze --python $SB/envs/a3_class_state-$n/bin/python > $W/logs/venv/freeze-$n.txt 2>/dev/null
done
