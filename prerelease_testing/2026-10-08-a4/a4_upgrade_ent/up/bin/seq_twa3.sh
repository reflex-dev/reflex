#!/usr/bin/env bash
# twitter prod + Redis: 0.10.0a3 baseline (sessions pickled in Redis by a3) + stale tab -> in-place upgrade with reflex[db]
# -> a4 prod against the SAME Redis (a3-pickled sessions must load on a4 after #7494 changed __getstate__).
set -u; . $(dirname $0)/common.sh
A=$W/twitter-redis; V=$SB/envs/a4_upgrade_ent-twa3; P=3614; RP=8609; S=$W/shots/twa3; T=$W/ctl/twa3.tok; C=$W/ctl/twa3
rm -rf $A/.web $A/reflex.lock $A/.states $A/reflex.db $T $C; mkdir -p $S $C
redis-server --port $RP --save '' --appendonly no > $W/logs/twa3-redis.log 2>&1 & RPID=$!; sleep 1
export REFLEX_REDIS_URL=redis://localhost:$RP REFLEX_API_URL=http://localhost:$P QA_USER_SUFFIX=t
# (unused) workers() { echo "granian processes: $(pgrep -f -c 'granian|reflex' ) total reflex/granian; workers: $(ps -eo pid,ppid,cmd | grep -E 'twitter|granian' | grep -v grep | awk '{print $2}' | sort | uniq -c | sort -rn | head -1)"; }
echo "### twa3 base $(date +%T)"; (cd $A && REFLEX_TELEMETRY_ENABLED=false $V/bin/reflex db migrate > $W/logs/twa3-base-migrate.log 2>&1; echo "migrate rc=$?")
$W/bin/run_app.sh $A $V $P $P $W/logs/twa3-base-prod.server.log --env prod || { kill $RPID; exit 1; }
ps -eo pid,ppid,pgid,cmd | grep -v grep | grep -E "$(cat $W/run/twitter-redis.pid)" > $W/logs/twa3-base-procs.txt; pstree -p $(cat $W/run/twitter-redis.pid) > $W/logs/twa3-base-pstree.txt 2>/dev/null; echo "granian workers spawned (a3): $(grep -c 'Spawning worker-' $W/logs/twa3-base-prod.server.log)"
$DRV $W/scripts/drive_twitter.py http://localhost:$P/ $S twa3-base-prod base $T 0.10.0a3 | summ
[ -f $T ] || { echo "BASE DRIVE LEFT NO TOKEN FILE - stopping (load: $(cut -d' ' -f1-3 /proc/loadavg))"; $W/bin/stop_app.sh $A $P; kill $RPID; exit 3; }
QA_EXPECT_SESSION=1 QA_STALE_USER=davet QA_STALE_FOLLOW=alicet $DRV $W/scripts/stale_tab_twitter.py http://localhost:$P/ $S twa3-stale-prod $C > $W/logs/twa3-stale.driver.log 2>&1 & ST=$!
for i in $(seq 1 180); do [ -f $C/ready ] && break; sleep 1; done; echo "stale tab ready: $([ -f $C/ready ] && echo yes || echo NO)"
redis-cli -p $RP dbsize; redis-cli -p $RP --scan | head -3
pkgsnap $A twa3-base; $W/bin/stop_app.sh $A $P; touch $C/down
echo "### twa3 upgrade $(date +%T)"; upgrade twa3 twa3 'reflex[db]==0.10.0a4' 'pydantic<2.14'
echo "### twa3 up $(date +%T)"; $W/bin/run_app.sh $A $V $P $P $W/logs/twa3-up-prod.server.log --env prod || { kill $RPID; exit 1; }
pstree -p $(cat $W/run/twitter-redis.pid) > $W/logs/twa3-up-pstree.txt 2>/dev/null; echo "granian workers spawned (a4): $(grep -c 'Spawning worker-' $W/logs/twa3-up-prod.server.log)"
pkgsnap $A twa3-up; diff $W/pkg/twa3-base.web.package.json $W/pkg/twa3-up.web.package.json > $W/pkg/twa3-base-to-up.package.diff; echo "package.json diff a3->a4: $(grep -E "^[<>]" $W/pkg/twa3-base-to-up.package.diff | tr -s " " | tr "\n" " ")"; diff -q $A/.web/package.json $A/reflex.lock/package.json && echo "reflex.lock/package.json == .web/package.json"
touch $C/up; for i in $(seq 1 240); do [ -f $C/done ] && break; sleep 1; done; wait $ST; summ < $W/logs/twa3-stale.driver.log
QA_EXPECT_SESSION=1 $DRV $W/scripts/drive_twitter.py http://localhost:$P/ $S twa3-up-prod up $T 0.10.0a4 | summ
QA_USER_SUFFIX=t2 $DRV $W/scripts/drive_twitter.py http://localhost:$P/ $S twa3-up-prod-base base $W/ctl/twa32.tok 0.10.0a4 | summ
cp $T $W/ctl/twa3-a3-saved.tok
$W/bin/stop_app.sh $A $P
$W/bin/stop_app.sh $A $P; kill $RPID
for t in base-prod up-prod; do echo "--- twa3-$t server-log warnings:"; logscan $W/logs/twa3-$t.server.log; done
echo "### twa3 done $(date +%T)"
