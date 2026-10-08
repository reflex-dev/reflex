#!/usr/bin/env bash
# form-designer: 0.9.12 baseline -> in-place upgrade to a4 (same venv/app dir/.web/reflex.lock/reflex.db/profile) -> prod -> cold.
set -u; . $(dirname $0)/common.sh
A=$W/form-designer; V=$SB/envs/a4_upgrade_ent-fd; FP=3600; BP=8600; P=$W/profiles/fd; S=$W/shots/fd; export FD_FIX_FIELD_NAME=1
rm -rf $A/.web $A/reflex.lock $A/reflex.db $A/.states $P; mkdir -p $S
echo "### fd base $(date +%T)"; (cd $A && REFLEX_TELEMETRY_ENABLED=false $V/bin/reflex db migrate > $W/logs/fd-base-migrate.log 2>&1; echo "migrate rc=$?")
$W/bin/run_app.sh $A $V $FP $BP $W/logs/fd-base.server.log || exit 1
$DRV $W/scripts/drive_form_designer.py http://localhost:$FP/ $S fd-base-full full $P 0.9.12 | summ
$DRV $W/scripts/drive_form_designer.py http://localhost:$FP/ $S fd-base-entry entry $P 0.9.12 | summ
$DRV $W/scripts/storage_probe.py http://localhost:$FP $S fd-base-persist-editor $P --path /edit/form/ --wait 6 --expect-text "Existing Forms" --forbid-writes | grep -E "^(PASS|FAIL)|CHANGING|idempotent write|n_changing_app"
pkgsnap $A fd-base; $W/bin/stop_app.sh $A $FP $BP
$SB/envs/driver/bin/python $W/scripts/dbdump.py $A/reflex.db > $W/logs/fd-db-base.txt
echo "### fd upgrade $(date +%T)"; upgrade fd fd 'reflex[db]==0.10.0a4'
echo "### fd up $(date +%T)"; $W/bin/run_app.sh $A $V $FP $BP $W/logs/fd-up.server.log || exit 1
pkgsnap $A fd-up; diff $W/pkg/fd-base.web.package.json $W/pkg/fd-up.web.package.json > $W/pkg/fd-base-to-up.package.diff; echo "package.json diff: $(grep -E '^[<>]' $W/pkg/fd-base-to-up.package.diff | tr -s ' ' | tr '\n' ' ')"
TOK=$($SB/envs/driver/bin/python -c "import json; print(json.load(open('$S/fd-base-persist-editor.json'))['end']['ls'].get('_auth_token',''))")
echo "auth token from base snapshot: ${TOK:0:12}..."
$DRV $W/scripts/storage_probe.py http://localhost:$FP $S fd-up-firstload-editor $P --path /edit/form/ --wait 6 --expect-text "Existing Forms" --keep "_auth_token=$TOK" --forbid-writes | grep -E "^(PASS|FAIL)|CHANGING|idempotent write|n_changing_app"
$DRV $W/scripts/drive_form_designer.py http://localhost:$FP/ $S fd-up-up up $P 0.10.0a4 | summ
$DRV $W/scripts/drive_form_designer.py http://localhost:$FP/ $S fd-up-entry entry $P 0.10.0a4 | summ
$W/bin/stop_app.sh $A $FP $BP
$SB/envs/driver/bin/python $W/scripts/dbdump.py $A/reflex.db > $W/logs/fd-db-up.txt
(cd $A && REFLEX_TELEMETRY_ENABLED=false $V/bin/reflex db makemigrations --message qa_probe > $W/logs/fd-up-makemigrations.log 2>&1; echo "makemigrations rc=$? version files: $(ls $A/alembic/versions | grep -c py)")
echo "### fd prod $(date +%T)"; REFLEX_API_URL=http://localhost:$FP $W/bin/run_app.sh $A $V $FP $FP $W/logs/fd-up-prod.server.log --env prod || exit 1
for r in /edit/form/1 /form/1 /responses/1 /nope /login; do echo "prod $r -> $(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:$FP$r)"; done
$DRV $W/scripts/drive_form_designer.py http://localhost:$FP/ $S fd-up-prod-up up $P 0.10.0a4 | summ
$DRV $W/scripts/drive_form_designer.py http://localhost:$FP/ $S fd-up-prod-entry entry $P 0.10.0a4 | summ
$W/bin/stop_app.sh $A $FP
echo "### fd cold $(date +%T)"; rm -rf $A/.web; $W/bin/run_app.sh $A $V $FP $BP $W/logs/fd-cold.server.log || exit 1
pkgsnap $A fd-cold; diff -q $W/pkg/fd-up.web.package.json $W/pkg/fd-cold.web.package.json && echo "cold package.json == up"; diff $W/pkg/fd-up.web.files $W/pkg/fd-cold.web.files > /dev/null && echo "cold file list == up" || diff $W/pkg/fd-up.web.files $W/pkg/fd-cold.web.files | head -5
$DRV $W/scripts/drive_form_designer.py http://localhost:$FP/ $S fd-cold-up up $P 0.10.0a4 | summ
$W/bin/stop_app.sh $A $FP $BP
for t in base up up-prod cold; do echo "--- fd-$t server-log warnings:"; logscan $W/logs/fd-$t.server.log; done
echo "### fd done $(date +%T)"
