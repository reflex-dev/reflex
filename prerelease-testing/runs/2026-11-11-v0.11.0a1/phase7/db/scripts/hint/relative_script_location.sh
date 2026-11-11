#!/bin/bash
# relative_script_location.sh <venv-dir>: a custom env.py that raises; hint shown only when alembic.ini's script_location is absolute.
V=$1; W=$(cd $(dirname $0)/../.. && pwd)/apps/hint_$(basename $V); rm -rf $W; mkdir -p $W/happ; cd $W; export REFLEX_TELEMETRY_ENABLED=false
printf 'import reflex as rx\nconfig = rx.Config(app_name="happ", db_url="sqlite:///reflex.db")\n' > rxconfig.py; touch happ/__init__.py
printf 'import reflex as rx\ndef index():\n    return rx.text("hi")\napp = rx.App()\napp.add_page(index)\n' > happ/happ.py
$V/bin/reflex db init > init.log 2>&1 || { echo "init failed"; exit 1; }
printf 'import os\nfrom alembic import context\nraise RuntimeError("custom env.py failed: " + os.environ.get("NOPE", "missing env var"))\n' > alembic/env.py
for loc in '%(here)s/alembic' 'alembic'; do sed -i "s|^script_location = .*|script_location = $loc|" alembic.ini
  $V/bin/reflex db status > status.log 2>&1; rc=$?
  echo "script_location = $loc -> reflex db status rc=$rc | hint shown: $(grep -c 'to write the current template' status.log) | traceback lines: $(grep -c '^Traceback\|^  File ' status.log)"; done
