#!/usr/bin/env bash
# Rebuild the a3-tester venv (reflex[db]==0.10.0a3, pydantic<2.14) from scratch, then run seq_twa3.sh (a3 -> a4 in place, twitter prod + Redis).
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a5_upgrade_ent/up; cd $SB
V=$SB/envs/a5_upgrade_ent-twa3
uv --no-config venv --clear -q --python 3.12 $V 2>&1 | grep -v UV_NATIVE
uv --no-config pip install -q --python $V/bin/python --prerelease=allow -r $W/twitter-redis/requirements.txt 'reflex[db]==0.10.0a3' 'pydantic<2.14' 2>&1 | grep -v UV_NATIVE
uv --no-config pip freeze --python $V/bin/python 2>/dev/null > $W/freeze/twa3-base.txt
echo "built: $(grep -E '^(reflex|reflex-base|sqlalchemy|greenlet|pydantic)==' $W/freeze/twa3-base.txt | tr '\n' ' ')"
$W/bin/seq_twa3.sh
$W/bin/ports.sh
