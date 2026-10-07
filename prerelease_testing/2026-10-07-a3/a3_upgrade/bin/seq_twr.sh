#!/usr/bin/env bash
# twitter prod + Redis: 0.9.12 baseline (sessions pickled in Redis by 0.9.12) + stale tab -> in-place upgrade with reflex[db]
# -> a3 prod against the SAME Redis (0.9 state must load) -> rollback to 0.9.12 against the same Redis (guide: sessions reset, no crash).
set -u; . $(dirname $0)/common.sh
A=$W/twitter-redis; V=$SB/envs/a3_upgrade-twr; P=3232; RP=8209; S=$W/shots/twr; T=$W/ctl/twr.tok; C=$W/ctl/twr
rm -rf $A/.web $A/reflex.lock $A/.states $A/reflex.db $T $C; mkdir -p $S $C
redis-server --port $RP --save '' --appendonly no > $W/logs/twr-redis.log 2>&1 & RPID=$!; sleep 1
export REFLEX_REDIS_URL=redis://localhost:$RP REFLEX_API_URL=http://localhost:$P QA_USER_SUFFIX=r
# (unused) workers() { echo "granian processes: $(pgrep -f -c 'granian|reflex' ) total reflex/granian; workers: $(ps -eo pid,ppid,cmd | grep -E 'twitter|granian' | grep -v grep | awk '{print $2}' | sort | uniq -c | sort -rn | head -1)"; }
echo "### twr base $(date +%T)"; (cd $A && REFLEX_TELEMETRY_ENABLED=false $V/bin/reflex db migrate > $W/logs/twr-base-migrate.log 2>&1; echo "migrate rc=$?")
$W/bin/run_app.sh $A $V $P $P $W/logs/twr-base-prod.server.log --env prod || { kill $RPID; exit 1; }
ps -eo pid,ppid,pgid,cmd | grep -v grep | grep -E "$(cat $W/run/twitter-redis.pid)" > $W/logs/twr-base-procs.txt; pstree -p $(cat $W/run/twitter-redis.pid) > $W/logs/twr-base-pstree.txt 2>/dev/null; echo "granian workers spawned (0.9.12): $(grep -c 'Spawning worker-' $W/logs/twr-base-prod.server.log)"
$DRV $W/scripts/drive_twitter.py http://localhost:$P/ $S twr-base-prod base $T 0.9.12 | summ
[ -f $T ] || { echo "BASE DRIVE LEFT NO TOKEN FILE - stopping (load: $(cut -d' ' -f1-3 /proc/loadavg))"; $W/bin/stop_app.sh $A $P; kill $RPID; exit 3; }
QA_EXPECT_SESSION=1 QA_STALE_USER=daver QA_STALE_FOLLOW=alicer $DRV $W/scripts/stale_tab_twitter.py http://localhost:$P/ $S twr-stale-prod $C > $W/logs/twr-stale.driver.log 2>&1 & ST=$!
for i in $(seq 1 180); do [ -f $C/ready ] && break; sleep 1; done; echo "stale tab ready: $([ -f $C/ready ] && echo yes || echo NO)"
redis-cli -p $RP dbsize; redis-cli -p $RP --scan | head -3
$W/bin/stop_app.sh $A $P; touch $C/down
echo "### twr upgrade $(date +%T)"; upgrade twr twr 'reflex[db]==0.10.0a3' 'pydantic<2.14'
echo "### twr up $(date +%T)"; $W/bin/run_app.sh $A $V $P $P $W/logs/twr-up-prod.server.log --env prod || { kill $RPID; exit 1; }
pstree -p $(cat $W/run/twitter-redis.pid) > $W/logs/twr-up-pstree.txt 2>/dev/null; echo "granian workers spawned (a3): $(grep -c 'Spawning worker-' $W/logs/twr-up-prod.server.log)"
touch $C/up; for i in $(seq 1 240); do [ -f $C/done ] && break; sleep 1; done; wait $ST; summ < $W/logs/twr-stale.driver.log
QA_EXPECT_SESSION=1 $DRV $W/scripts/drive_twitter.py http://localhost:$P/ $S twr-up-prod up $T 0.10.0a3 | summ
QA_USER_SUFFIX=r2 $DRV $W/scripts/drive_twitter.py http://localhost:$P/ $S twr-up-prod-base base $W/ctl/twr2.tok 0.10.0a3 | summ
cp $T $W/ctl/twr-a3-saved.tok
$W/bin/stop_app.sh $A $P
echo "### twr rollback to 0.9.12 against the same Redis $(date +%T)"
(cd $SB && uv --no-config pip sync --python $V/bin/python $W/freeze/twr-base.txt 2>&1 | grep -v UV_NATIVE > $W/logs/twr-rollback.install.log; uv --no-config pip freeze --python $V/bin/python 2>/dev/null > $W/freeze/twr-rollback.txt)
diff $W/freeze/twr-base.txt $W/freeze/twr-rollback.txt > /dev/null && echo "rollback venv == base freeze" || diff $W/freeze/twr-base.txt $W/freeze/twr-rollback.txt | head -5
$W/bin/run_app.sh $A $V $P $P $W/logs/twr-rollback-prod.server.log --env prod || { kill $RPID; exit 1; }
QA_EXPECT_SESSION=0 $DRV $W/scripts/drive_twitter.py http://localhost:$P/ $S twr-rollback-prod up $T 0.9.12 | summ
$W/bin/stop_app.sh $A $P; kill $RPID
for t in base-prod up-prod rollback-prod; do echo "--- twr-$t server-log warnings:"; logscan $W/logs/twr-$t.server.log; done
echo "### twr done $(date +%T)"
