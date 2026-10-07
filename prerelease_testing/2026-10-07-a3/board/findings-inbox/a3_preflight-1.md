ITEM: a3_preflight
KIND: reverify
REF: N-001
TITLE: Fresh reflex[db] installs now bring greenlet; rx.Model and reflex db commands work
SEVERITY: high
STATUS: fixed
REGRESSION_VS_0.9.12: no
REGRESSION_VS_0.10.0a2: no
REPRO: uv --no-config venv --python 3.1x v && uv --no-config pip install --python v/bin/python --prerelease=allow 'reflex[db]==0.10.0a3' 'pydantic<2.14' (and pip --pre), then greenlet_probe.py and reflex db init/makemigrations/migrate in a3_preflight/apps/dbcli
EVIDENCE: a3_preflight/logs/03-n001-fresh-installs.txt (8/8: sqlalchemy 2.1.4 + greenlet 3.5.6 via the db extra), logs/04-n001-db-cli.txt, logs/dbcli-prod.{log,json}
ROOT_CAUSE_GUESS: fixed by #7466 (greenlet>=3.3 in the db extra, visible in the published METADATA)
