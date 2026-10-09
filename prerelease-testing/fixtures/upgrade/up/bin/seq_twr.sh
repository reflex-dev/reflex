#!/usr/bin/env bash
# twitter (PySocial) prod + Redis: baseline (sessions pickled in Redis by the base version) + a stale tab kept open across
# stop -> in-place upgrade to NEW_VERSION -> prod against the SAME Redis (old pickles must load without re-login) -> new users
# -> optional rollback to the base freeze against the same Redis (sessions touched by the new version reset, no crash).
# KEY selects the venv / log prefix: twr = from BASE_VERSION (a stable), twa = alpha-to-alpha (build it with
#   BASE_VERSION=<prev alpha> UP_EXTRA=... build_base_venvs.sh twa:twitter-redis, run with KEY=twa ROLLBACK=0).
# Ports: P (prod single port, default 3500), RP (Redis, default 8499).
set -u; . "$(dirname "$0")/common.sh"
K=${KEY:-twr}; A=$U/apps/twitter-redis; V=$(venv_of "$K"); P=${P:-3500}; RP=${RP:-8499}; S=$U/shots/$K; T=$U/ctl/$K.tok; C=$U/ctl/$K
SFX=${QA_USER_SUFFIX:-${K:2:1}}; [ -z "$SFX" ] && SFX=r
rm -rf "$A/.web" "$A/reflex.lock" "$A/.states" "$A/reflex.db" "$T" "$C"; mkdir -p "$S" "$C"
setsid redis-server --port $RP --bind 127.0.0.1 --save '' --appendonly no > "$U/logs/$K-redis.log" 2>&1 < /dev/null & RPID=$!; sleep 1
trap 'redis-cli -p $RP shutdown nosave >/dev/null 2>&1; kill $RPID 2>/dev/null' EXIT
export REFLEX_REDIS_URL=redis://localhost:$RP REFLEX_API_URL=http://localhost:$P QA_USER_SUFFIX=$SFX
# upstream twitter ships no alembic dir: create it with the BASE version, as its user would have
[ -d "$A/alembic" ] || (cd "$A" && "$V/bin/reflex" db init > "$U/logs/$K-base-dbinit.log" 2>&1; echo "db init rc=$?")
echo "### $K base $BASE_VERSION $(date +%T)"; (cd "$A" && "$V/bin/reflex" db migrate > "$U/logs/$K-base-migrate.log" 2>&1; echo "migrate rc=$?")
"$U/bin/run_app.sh" "$A" "$V" $P $P "$U/logs/$K-base-prod.server.log" --env prod || exit 1
echo "granian workers spawned (base): $(grep -c 'Spawning worker-' "$U/logs/$K-base-prod.server.log")"
$DRV "$U/scripts/drive_twitter.py" http://localhost:$P/ "$S" $K-base-prod base "$T" "$BASE_VERSION" | summ
[ -f "$T" ] || { echo "BASE DRIVE LEFT NO TOKEN FILE - stopping (load: $(cut -d' ' -f1-3 /proc/loadavg))"; "$U/bin/stop_app.sh" "$A" $P; exit 3; }
QA_EXPECT_SESSION=1 QA_STALE_USER=dave$SFX QA_STALE_FOLLOW=alice$SFX $DRV "$U/scripts/stale_tab_twitter.py" http://localhost:$P/ "$S" $K-stale-prod "$C" > "$U/logs/$K-stale.driver.log" 2>&1 & ST=$!
for i in $(seq 1 180); do [ -f "$C/ready" ] && break; sleep 1; done; echo "stale tab ready: $([ -f "$C/ready" ] && echo yes || echo NO)"
echo "redis keys: $(redis-cli -p $RP dbsize)"
pkgsnap "$A" $K-base; "$U/bin/stop_app.sh" "$A" $P; touch "$C/down"
echo "### $K upgrade -> $NEW_VERSION $(date +%T)"; upgrade "$K" "$K" "reflex[db]==$NEW_VERSION" ${UP_EXTRA:-}
echo "### $K up $(date +%T)"; "$U/bin/run_app.sh" "$A" "$V" $P $P "$U/logs/$K-up-prod.server.log" --env prod || exit 1
echo "granian workers spawned (up): $(grep -c 'Spawning worker-' "$U/logs/$K-up-prod.server.log")"
pkgsnap "$A" $K-up; pkgdiff $K-base $K-up
touch "$C/up"; for i in $(seq 1 240); do [ -f "$C/done" ] && break; sleep 1; done; wait $ST; summ < "$U/logs/$K-stale.driver.log"
QA_EXPECT_SESSION=1 $DRV "$U/scripts/drive_twitter.py" http://localhost:$P/ "$S" $K-up-prod up "$T" "$NEW_VERSION" | summ
QA_USER_SUFFIX=${SFX}2 $DRV "$U/scripts/drive_twitter.py" http://localhost:$P/ "$S" $K-up-prod-base base "$U/ctl/${K}2.tok" "$NEW_VERSION" | summ
"$U/bin/stop_app.sh" "$A" $P
if [ "${ROLLBACK:-1}" = 1 ]; then
  echo "### $K rollback to $BASE_VERSION against the same Redis $(date +%T)"
  uvq pip sync --python "$V/bin/python" "$U/freeze/$K-base.txt" > "$U/logs/$K-rollback.install.log"
  uvq pip freeze --python "$V/bin/python" > "$U/freeze/$K-rollback.txt"
  diff -q "$U/freeze/$K-base.txt" "$U/freeze/$K-rollback.txt" > /dev/null && echo "rollback venv == base freeze" || diff "$U/freeze/$K-base.txt" "$U/freeze/$K-rollback.txt" | head -5
  "$U/bin/run_app.sh" "$A" "$V" $P $P "$U/logs/$K-rollback-prod.server.log" --env prod || exit 1
  QA_EXPECT_SESSION=0 $DRV "$U/scripts/drive_twitter.py" http://localhost:$P/ "$S" $K-rollback-prod up "$T" "$BASE_VERSION" | summ
  "$U/bin/stop_app.sh" "$A" $P
fi
for t in base-prod up-prod rollback-prod; do [ -f "$U/logs/$K-$t.server.log" ] && { echo "--- $K-$t server-log warnings:"; logscan "$U/logs/$K-$t.server.log"; }; done
echo "### $K done $(date +%T)"
