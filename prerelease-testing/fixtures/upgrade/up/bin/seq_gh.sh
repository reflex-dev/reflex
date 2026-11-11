#!/usr/bin/env bash
# github-stats (rx.LocalStorage, recharts, bg task, widget on_load reading router.page.params): BASE_VERSION baseline (fresh
# profile) -> in-place upgrade -> persist (same profile, first-load storage probe) -> prod -> cold. GitHub GraphQL is replaced
# by scripts/github_stub.py (QA patch github-stats_fetchers.diff reads QA_GITHUB_GRAPHQL_URL). Ports FP/BP/STUBP (3492/8492/8498).
set -u; . "$(dirname "$0")/common.sh"
A=$U/apps/github-stats; V=$(venv_of gh); FP=${FP:-3492}; BP=${BP:-8492}; STUBP=${STUBP:-8498}; P=$U/profiles/gh; S=$U/shots/gh; STUB=http://127.0.0.1:$STUBP
export QA_GITHUB_GRAPHQL_URL=$STUB/graphql GITHUB_API_TOKEN=qa-dummy-token
rm -rf "$A/.web" "$A/reflex.lock" "$A/.states" "$P" "$U/profiles/gh-cold"; mkdir -p "$S"
"$DPY" "$U/scripts/github_stub.py" $STUBP > "$U/logs/gh-stub.log" 2>&1 & STUBPID=$!; sleep 1
trap 'kill $STUBPID 2>/dev/null' EXIT
echo "### gh base $BASE_VERSION $(date +%T)"; "$U/bin/run_app.sh" "$A" "$V" $FP $BP "$U/logs/gh-base.server.log" || exit 1
$DRV "$U/scripts/drive_github_stats.py" http://localhost:$FP/ "$S" gh-base fresh "$P" $STUB | summ
pkgsnap "$A" gh-base; "$U/bin/stop_app.sh" "$A" $FP $BP
echo "### gh upgrade -> $NEW_VERSION $(date +%T)"; upgrade gh gh "reflex[db]==$NEW_VERSION" ${UP_EXTRA:-}
echo "### gh up $(date +%T)"; "$U/bin/run_app.sh" "$A" "$V" $FP $BP "$U/logs/gh-up.server.log" || exit 1
pkgsnap "$A" gh-up; pkgdiff gh-base gh-up
$DRV "$U/scripts/storage_probe.py" http://localhost:$FP "$S" gh-up-firstload-home "$P" --wait 8 --expect-text "alice" --forbid-writes | grep -E "^(PASS|FAIL)|CHANGING|idempotent write"
$DRV "$U/scripts/drive_github_stats.py" http://localhost:$FP/ "$S" gh-up persist "$P" $STUB | summ
"$U/bin/stop_app.sh" "$A" $FP $BP
[ "${SKIP_PROD:-0}" = 1 ] || {
echo "### gh prod $(date +%T)"; REFLEX_API_URL=http://localhost:$FP "$U/bin/run_app.sh" "$A" "$V" $FP $FP "$U/logs/gh-up-prod.server.log" --env prod || exit 1
$DRV "$U/scripts/drive_github_stats.py" http://localhost:$FP/ "$S" gh-up-prod persist "$P" $STUB | summ
"$U/bin/stop_app.sh" "$A" $FP; }
[ "${SKIP_COLD:-0}" = 1 ] || {
echo "### gh cold $(date +%T)"; rm -rf "$A/.web"; "$U/bin/run_app.sh" "$A" "$V" $FP $BP "$U/logs/gh-cold.server.log" || exit 1
pkgsnap "$A" gh-cold; pkgdiff gh-up gh-cold
$DRV "$U/scripts/drive_github_stats.py" http://localhost:$FP/ "$S" gh-cold fresh "$U/profiles/gh-cold" $STUB | summ
"$U/bin/stop_app.sh" "$A" $FP $BP; }
for t in base up up-prod cold; do [ -f "$U/logs/gh-$t.server.log" ] && { echo "--- gh-$t server-log warnings:"; logscan "$U/logs/gh-$t.server.log"; }; done
echo "### gh done $(date +%T)"
