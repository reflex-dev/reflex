#!/usr/bin/env bash
# twitter dev with the default disk state manager: BASE_VERSION baseline -> in-place upgrade -> up (users log in again:
# `reflex run` wipes .states in dev on every version) -> cold with new users. Ports FP/BP (default 3496/8496).
set -u; . "$(dirname "$0")/common.sh"
A=$U/apps/twitter; V=$(venv_of tw); FP=${FP:-3496}; BP=${BP:-8496}; S=$U/shots/tw; T=$U/ctl/tw.tok
rm -rf "$A/.web" "$A/reflex.lock" "$A/.states" "$A/reflex.db" "$T"; mkdir -p "$S"
[ -d "$A/alembic" ] || (cd "$A" && "$V/bin/reflex" db init > "$U/logs/tw-base-dbinit.log" 2>&1; echo "db init rc=$?")
echo "### tw base $BASE_VERSION $(date +%T)"; (cd "$A" && "$V/bin/reflex" db migrate > "$U/logs/tw-base-migrate.log" 2>&1; echo "migrate rc=$?")
"$U/bin/run_app.sh" "$A" "$V" $FP $BP "$U/logs/tw-base.server.log" || exit 1
$DRV "$U/scripts/drive_twitter.py" http://localhost:$FP/ "$S" tw-base base "$T" "$BASE_VERSION" | summ
pkgsnap "$A" tw-base; "$U/bin/stop_app.sh" "$A" $FP $BP
"$DPY" "$U/scripts/dbdump.py" "$A/reflex.db" > "$U/logs/tw-db-base.txt"
echo "### tw upgrade -> $NEW_VERSION $(date +%T)"; upgrade tw tw "reflex[db]==$NEW_VERSION" ${UP_EXTRA:-}
(cd "$A" && "$V/bin/reflex" db migrate > "$U/logs/tw-up-migrate.log" 2>&1; echo "migrate after upgrade rc=$?")
echo "### tw up $(date +%T)"; "$U/bin/run_app.sh" "$A" "$V" $FP $BP "$U/logs/tw-up.server.log" || exit 1
pkgsnap "$A" tw-up; pkgdiff tw-base tw-up
QA_EXPECT_SESSION=0 $DRV "$U/scripts/drive_twitter.py" http://localhost:$FP/ "$S" tw-up up "$T" "$NEW_VERSION" | summ
"$U/bin/stop_app.sh" "$A" $FP $BP
"$DPY" "$U/scripts/dbdump.py" "$A/reflex.db" > "$U/logs/tw-db-up.txt"
echo "### tw cold $(date +%T)"; rm -rf "$A/.web"; "$U/bin/run_app.sh" "$A" "$V" $FP $BP "$U/logs/tw-cold.server.log" || exit 1
pkgsnap "$A" tw-cold; pkgdiff tw-up tw-cold
QA_USER_SUFFIX=c $DRV "$U/scripts/drive_twitter.py" http://localhost:$FP/ "$S" tw-cold-base base "$U/ctl/tw-cold.tok" "$NEW_VERSION" | summ
"$U/bin/stop_app.sh" "$A" $FP $BP
for t in base up cold; do echo "--- tw-$t server-log warnings:"; logscan "$U/logs/tw-$t.server.log"; done
echo "### tw done $(date +%T)"
