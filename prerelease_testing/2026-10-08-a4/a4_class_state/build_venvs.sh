#!/bin/bash
# Build this cluster's venvs (PyPI only; run from $SB with --no-config).
set -x
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/a4_class_state
cd $SB
mk() { # name python pkgs...
  local n=$1 py=$2; shift 2
  uv --no-config venv --python $py $SB/envs/a4_class_state-$n &&
  uv --no-config pip install --python $SB/envs/a4_class_state-$n/bin/python --prerelease=allow "$@" &&
  uv --no-config pip freeze --python $SB/envs/a4_class_state-$n/bin/python > $W/logs/venv/freeze-$n.txt
}
T="pytest pytest-mock pytest-asyncio"
[ "$1" = tp ] || mk a4 3.12 'reflex[db,testing]==0.10.0a4' 'reflex-base==0.10.0a4' 'pydantic<2.14' $T 'playwright==1.63.0'
[ "$1" = tp ] || mk a4-py311 3.11 'reflex[db]==0.10.0a4' 'reflex-base==0.10.0a4' 'pydantic<2.14' $T
[ "$1" = tp ] || mk a4-py314 3.14 'reflex[db]==0.10.0a4' 'reflex-base==0.10.0a4' 'pydantic<2.14' $T
[ "$1" = tp ] || mk a3 3.12 'reflex[db,testing]==0.10.0a3' 'reflex-base==0.10.0a3' 'pydantic<2.14' $T 'playwright==1.63.0'
[ "$1" = tp ] || mk s912 3.12 'reflex[db,testing]==0.9.12' 'reflex-base==0.9.12' 'pydantic<2.14' greenlet $T 'playwright==1.63.0'
# third-party sweep packages (list from prerelease_testing/2026-10-07-a3/a3_events_tp/tp/packages.txt) on a4
if [ "$1" = tp ]; then
mk tp 3.12 'reflex[db]==0.10.0a4' 'reflex-base==0.10.0a4' 'reflex-hosting-cli==0.2.0a1' 'pydantic<2.14' $(cat /home/user/reflex/prerelease_testing/2026-10-07-a3/a3_events_tp/tp/packages.txt) authlib $T 'google-api-python-client>=2.184.0'
fi
