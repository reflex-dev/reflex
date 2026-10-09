#!/usr/bin/env bash
# Baseline venvs for the in-place upgrades = what a user of BASE_VERSION has: -r <app>/requirements.txt 'reflex==$BASE_VERSION' $BASE_EXTRA
# Usage: build_base_venvs.sh [key:app ...]   (default: fd:form-designer gh:github-stats twr:twitter-redis)
#   other keys used by the seq scripts: ck:clock tw:twitter, and seq_app.sh uses the app name as key (e.g. counter:counter)
# Env: BASE_VERSION (default $PREV_VERSION), BASE_EXTRA (e.g. 'sqlalchemy<2.1' to mimic a 0.9.12 install made before
#      SQLAlchemy 2.1, as the 0.10 alpha passes did), PY (default 3.12). Freeze -> up/freeze/<key>-base.txt
set -u; . "$(dirname "$0")/common.sh"
for spec in ${@:-fd:form-designer gh:github-stats twr:twitter-redis}; do
  k=${spec%%:*}; app=${spec#*:}; V=$(venv_of "$k"); rm -rf "$V"
  uvq venv -q --python "${PY:-3.12}" "$V"
  uvq pip install -q --python "$V/bin/python" $(pre_flag "$BASE_VERSION") -r "$U/apps/$app/requirements.txt" "reflex==$BASE_VERSION" ${BASE_EXTRA:-}
  uvq pip freeze --python "$V/bin/python" > "$U/freeze/$k-base.txt"
  echo "$k ($app): $(grep -E '^(reflex|reflex-base|sqlalchemy|greenlet|sqlmodel|pydantic|reflex-local-auth)==' "$U/freeze/$k-base.txt" | tr '\n' ' ')"
done
