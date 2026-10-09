#!/usr/bin/env bash
# form-designer (reflex[db] + reflex-local-auth): BASE_VERSION baseline -> in-place upgrade to NEW_VERSION (same venv / app dir /
# .web / reflex.lock / reflex.db / Chromium profile) -> storage first-load probe -> drive -> prod (routes + drive) -> cold rebuild.
# Ports FP/BP (default 3490/8490). Prereq: bin/stage.sh, up/bin/build_base_venvs.sh fd:form-designer
set -u; . "$(dirname "$0")/common.sh"
A=$U/apps/form-designer; V=$(venv_of fd); FP=${FP:-3490}; BP=${BP:-8490}; P=$U/profiles/fd; S=$U/shots/fd; export FD_FIX_FIELD_NAME=1
rm -rf "$A/.web" "$A/reflex.lock" "$A/reflex.db" "$A/.states" "$P"; mkdir -p "$S"
echo "### fd base $BASE_VERSION $(date +%T)"; (cd "$A" && "$V/bin/reflex" db migrate > "$U/logs/fd-base-migrate.log" 2>&1; echo "migrate rc=$?")
"$U/bin/run_app.sh" "$A" "$V" $FP $BP "$U/logs/fd-base.server.log" || exit 1
$DRV "$U/scripts/drive_form_designer.py" http://localhost:$FP/ "$S" fd-base-full full "$P" "$BASE_VERSION" | summ
$DRV "$U/scripts/drive_form_designer.py" http://localhost:$FP/ "$S" fd-base-entry entry "$P" "$BASE_VERSION" | summ
$DRV "$U/scripts/storage_probe.py" http://localhost:$FP "$S" fd-base-persist-editor "$P" --path /edit/form/ --wait 6 --expect-text "Existing Forms" --forbid-writes | grep -E "^(PASS|FAIL)|CHANGING|idempotent write|n_changing_app"
pkgsnap "$A" fd-base; "$U/bin/stop_app.sh" "$A" $FP $BP
"$DPY" "$U/scripts/dbdump.py" "$A/reflex.db" > "$U/logs/fd-db-base.txt"
echo "### fd upgrade -> $NEW_VERSION $(date +%T)"; upgrade fd fd "reflex[db]==$NEW_VERSION" ${UP_EXTRA:-}
echo "### fd up $(date +%T)"; "$U/bin/run_app.sh" "$A" "$V" $FP $BP "$U/logs/fd-up.server.log" || exit 1
pkgsnap "$A" fd-up; pkgdiff fd-base fd-up
TOK=$("$DPY" -c "import json,sys; print(json.load(open(sys.argv[1]))['end']['ls'].get('_auth_token',''))" "$S/fd-base-persist-editor.json")
echo "auth token from base snapshot: ${TOK:0:12}..."
$DRV "$U/scripts/storage_probe.py" http://localhost:$FP "$S" fd-up-firstload-editor "$P" --path /edit/form/ --wait 6 --expect-text "Existing Forms" --keep "_auth_token=$TOK" --forbid-writes | grep -E "^(PASS|FAIL)|CHANGING|idempotent write|n_changing_app"
$DRV "$U/scripts/drive_form_designer.py" http://localhost:$FP/ "$S" fd-up-up up "$P" "$NEW_VERSION" | summ
$DRV "$U/scripts/drive_form_designer.py" http://localhost:$FP/ "$S" fd-up-entry entry "$P" "$NEW_VERSION" | summ
"$U/bin/stop_app.sh" "$A" $FP $BP
"$DPY" "$U/scripts/dbdump.py" "$A/reflex.db" > "$U/logs/fd-db-up.txt"
(cd "$A" && "$V/bin/reflex" db makemigrations --message qa_probe > "$U/logs/fd-up-makemigrations.log" 2>&1; echo "makemigrations rc=$? version files: $(ls "$A/alembic/versions" | grep -c '\.py$') (expected 2: no new revision)")
[ "${SKIP_PROD:-0}" = 1 ] || {
echo "### fd prod $(date +%T)"; REFLEX_API_URL=http://localhost:$FP "$U/bin/run_app.sh" "$A" "$V" $FP $FP "$U/logs/fd-up-prod.server.log" --env prod || exit 1
for r in /edit/form/1 /form/1 /responses/1 /nope /login; do echo "prod $r -> $(http_code http://localhost:$FP$r)"; done
$DRV "$U/scripts/drive_form_designer.py" http://localhost:$FP/ "$S" fd-up-prod-up up "$P" "$NEW_VERSION" | summ
$DRV "$U/scripts/drive_form_designer.py" http://localhost:$FP/ "$S" fd-up-prod-entry entry "$P" "$NEW_VERSION" | summ
"$U/bin/stop_app.sh" "$A" $FP; }
[ "${SKIP_COLD:-0}" = 1 ] || {
echo "### fd cold $(date +%T)"; rm -rf "$A/.web"; "$U/bin/run_app.sh" "$A" "$V" $FP $BP "$U/logs/fd-cold.server.log" || exit 1
pkgsnap "$A" fd-cold; pkgdiff fd-up fd-cold
$DRV "$U/scripts/drive_form_designer.py" http://localhost:$FP/ "$S" fd-cold-up up "$P" "$NEW_VERSION" | summ
"$U/bin/stop_app.sh" "$A" $FP $BP; }
for t in base up up-prod cold; do [ -f "$U/logs/fd-$t.server.log" ] && { echo "--- fd-$t server-log warnings:"; logscan "$U/logs/fd-$t.server.log"; }; done
echo "### fd done $(date +%T)"
