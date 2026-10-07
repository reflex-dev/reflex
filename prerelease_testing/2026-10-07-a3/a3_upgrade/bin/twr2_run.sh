#!/usr/bin/env bash
# a2 -> a3 in place, twitter prod + Redis: venv built like an a2 tester had it (reflex[db]==0.10.0a2 + greenlet added by hand, N-001).
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a3_upgrade; cd $SB
V=$SB/envs/a3_upgrade-twr2
uv --no-config venv --clear -q --python 3.12 $V 2>&1 | grep -v UV_NATIVE
uv --no-config pip install -q --python $V/bin/python --prerelease=allow -r $W/twitter-redis/requirements.txt 'reflex[db]==0.10.0a2' greenlet 'pydantic<2.14' 2>&1 | grep -v UV_NATIVE
uv --no-config pip freeze --python $V/bin/python 2>/dev/null > $W/freeze/twr2-base.txt
echo "built: $(grep -E "^(reflex|reflex-base|sqlalchemy|greenlet|sqlmodel)==" $W/freeze/twr2-base.txt | tr "\n" " ") load $(cut -d" " -f1-3 /proc/loadavg)"
$W/bin/seq_twr2.sh
$W/bin/ports.sh
