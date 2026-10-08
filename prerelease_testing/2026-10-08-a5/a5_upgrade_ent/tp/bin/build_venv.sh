#!/usr/bin/env bash
# a5 + the 22 third-party packages of the a3 sweep (same spec as a3_events_tp NOTES "Rerun (third-party)", minus test tools)
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; TW=$SB/apps/a5_upgrade_ent/tp; V=$SB/envs/a5_upgrade_ent-tp; cd $SB
uv --no-config venv -q --clear --python 3.12 $V 2>&1 | grep -v UV_NATIVE
uv --no-config pip install --python $V/bin/python --prerelease=allow 'reflex[db]==0.10.0a5' 'reflex-base==0.10.0a5' 'reflex-hosting-cli==0.2.0a1' 'pydantic<2.14' \
  $(cat $TW/packages.txt) authlib 'google-api-python-client>=2.184.0' 2>&1 | grep -v UV_NATIVE | tail -3
uv --no-config pip freeze --python $V/bin/python 2>/dev/null > $TW/logs/a5-tp-freeze.txt
uv --no-config pip check --python $V/bin/python 2>&1 | grep -v UV_NATIVE | tail -3
