#!/usr/bin/env bash
# twitter prod + Redis: 0.10.0a2 baseline (sessions pickled in Redis by a2) + stale tab -> in-place upgrade with reflex[db]
# -> a3 prod against the SAME Redis (a2-pickled sessions must load on a3 after #7494 changed __getstate__).
set -u; . $(dirname $0)/common.sh
A=$W/twitter-redis; V=$SB/envs/a3_upgrade-twr2; P=3232; RP=8209; S=$W/shots/twr2; T=$W/ctl/twr2.tok; C=$W/ctl/twr2
rm -rf $A/.web $A/reflex.lock $A/.states $A/reflex.db $T $C; mkdir -p $S $C
redis-server --port $RP --save '' --appendonly no > $W/logs/twr2-redis.log 2>&1 & RPID=$!; sleep 1
export REFLEX_REDIS_URL=redis://localhost:$RP REFLEX_API_URL=http://localhost:$P QA_USER_SUFFIX=s
# (unused) workers() { echo "granian processes: $(pgrep -f -c 'granian|reflex' ) total reflex/granian; workers: $(ps -eo pid,ppid,cmd | grep -E 'twitter|granian' | grep -v grep | awk '{print $2}' | sort | uniq -c | sort -rn | head -1)"; }
echo "### twr2 base $(date +%T)"; (cd $A && REFLEX_TELEMETRY_ENABLED=false $V/bin/reflex db migrate > $W/logs/twr2-base-migrate.log 2>&1; echo "migrate rc=$?")
$W/bin/run_app.sh $A $V $P $P $W/logs/twr2-base-prod.server.log --env prod || { kill $RPID; exit 1; }
ps -eo pid,ppid,pgid,cmd | grep -v grep | grep -E "$(cat $W/run/twitter-redis.pid)" > $W/logs/twr2-base-procs.txt; pstree -p $(cat $W/run/twitter-redis.pid) > $W/logs/twr2-base-pstree.txt 2>/dev/null; echo "granian workers spawned (a2): $(grep -c 'Spawning worker-' $W/logs/twr2-base-prod.server.log)"
$DRV $W/scripts/drive_twitter.py http://localhost:$P/ $S twr2-base-prod base $T 0.10.0a2 | summ
[ -f $T ] || { echo "BASE DRIVE LEFT NO TOKEN FILE - stopping (load: $(cut -d' ' -f1-3 /proc/loadavg))"; $W/bin/stop_app.sh $A $P; kill $RPID; exit 3; }
QA_EXPECT_SESSION=1 QA_STALE_USER=daves QA_STALE_FOLLOW=alices $DRV $W/scripts/stale_tab_twitter.py http://localhost:$P/ $S twr2-stale-prod $C > $W/logs/twr2-stale.driver.log 2>&1 & ST=$!
for i in $(seq 1 180); do [ -f $C/ready ] && break; sleep 1; done; echo "stale tab ready: $([ -f $C/ready ] && echo yes || echo NO)"
redis-cli -p $RP dbsize; redis-cli -p $RP --scan | head -3
$W/bin/stop_app.sh $A $P; touch $C/down
echo "### twr2 upgrade $(date +%T)"; upgrade twr2 twr2 'reflex[db]==0.10.0a3' 'pydantic<2.14'
echo "### twr2 up $(date +%T)"; $W/bin/run_app.sh $A $V $P $P $W/logs/twr2-up-prod.server.log --env prod || { kill $RPID; exit 1; }
pstree -p $(cat $W/run/twitter-redis.pid) > $W/logs/twr2-up-pstree.txt 2>/dev/null; echo "granian workers spawned (a3): $(grep -c 'Spawning worker-' $W/logs/twr2-up-prod.server.log)"
touch $C/up; for i in $(seq 1 240); do [ -f $C/done ] && break; sleep 1; done; wait $ST; summ < $W/logs/twr2-stale.driver.log
QA_EXPECT_SESSION=1 $DRV $W/scripts/drive_twitter.py http://localhost:$P/ $S twr2-up-prod up $T 0.10.0a3 | summ
QA_USER_SUFFIX=s2 $DRV $W/scripts/drive_twitter.py http://localhost:$P/ $S twr2-up-prod-base base $W/ctl/twr22.tok 0.10.0a3 | summ
cp $T $W/ctl/twr2-a3-saved.tok
$W/bin/stop_app.sh $A $P
$W/bin/stop_app.sh $A $P; kill $RPID
for t in base-prod up-prod; do echo "--- twr2-$t server-log warnings:"; logscan $W/logs/twr2-$t.server.log; done
echo "### twr2 done $(date +%T)"
