#!/usr/bin/env bash
# Rebuild the 0.9.12 twitter-redis venv (uv venv --clear) and rerun seq_twr.sh (attempt 2; attempt 1 baseline timed out under load ~20).
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a3_upgrade; cd $SB
until grep -q "^### json2 done" $W/logs/jsondrain-followup2.txt 2>/dev/null; do sleep 5; done
V=$SB/envs/a3_upgrade-twr
uv --no-config venv --clear -q --python 3.12 $V 2>&1 | grep -v UV_NATIVE
uv --no-config pip install -q --python $V/bin/python -r $W/twitter-redis/requirements.txt 'reflex==0.9.12' 'sqlalchemy<2.1' 2>&1 | grep -v UV_NATIVE
uv --no-config pip freeze --python $V/bin/python 2>/dev/null > $W/freeze/twr-base.txt
echo "rebuilt: $(grep -E "^(reflex|reflex-base|sqlalchemy|greenlet)==" $W/freeze/twr-base.txt | tr "\n" " ") load $(cut -d" " -f1-3 /proc/loadavg)"
$W/bin/seq_twr.sh
$W/bin/ports.sh
