#!/usr/bin/env bash
# Third-party venv = NEW_VERSION + the 22 packages of tp/packages.txt (pinned) + authlib + google-api-python-client.
# Usage: build_venv.sh [venv-name] (default $VENV_PREFIX-tp). Env: TP_VERSION (default $NEW_VERSION), TP_EXTRA (e.g. 'pydantic<2.14',
# needed by the 0.10 alphas). Freeze -> tp/logs/<venv>-freeze.txt
set -u; . "$(dirname "$0")/../../bin/env.sh"; TW=$(cd "$(dirname "$0")/.." && pwd); V=$SB/envs/${1:-$VENV_PREFIX-tp}; X=${TP_VERSION:-$NEW_VERSION}
mkdir -p $TW/logs
uvq venv -q --clear --python ${PY:-3.12} $V
uvq pip install --python $V/bin/python $(pre_flag $X) "reflex[db]==$X" "reflex-base==$X" ${TP_EXTRA:-} \
  $(cat $TW/packages.txt) authlib 'google-api-python-client>=2.184.0' | tail -3
uvq pip freeze --python $V/bin/python > $TW/logs/$(basename $V)-freeze.txt
uvq pip check --python $V/bin/python | tail -3
