#!/usr/bin/env bash
# twitter dev (disk state manager): 0.9.12 baseline -> in-place upgrade -> a3 -> cold.
set -u; . $(dirname $0)/common.sh
A=$W/twitter; V=$SB/envs/a3_upgrade-tw; FP=3230; BP=8230; S=$W/shots/tw; T=$W/ctl/tw.tok
rm -rf $A/.web $A/reflex.lock $A/.states $A/reflex.db $T; mkdir -p $S
echo "### tw base $(date +%T)"; (cd $A && REFLEX_TELEMETRY_ENABLED=false $V/bin/reflex db migrate > $W/logs/tw-base-migrate.log 2>&1; echo "migrate rc=$?")
$W/bin/run_app.sh $A $V $FP $BP $W/logs/tw-base.server.log || exit 1
$DRV $W/scripts/drive_twitter.py http://localhost:$FP/ $S tw-base base $T 0.9.12 | summ
pkgsnap $A tw-base; $W/bin/stop_app.sh $A $FP $BP
$SB/envs/driver/bin/python $W/scripts/dbdump.py $A/reflex.db > $W/logs/tw-db-base.txt
echo "### tw upgrade $(date +%T)"; upgrade tw tw 'reflex==0.10.0a3' 'pydantic<2.14'
(cd $A && REFLEX_TELEMETRY_ENABLED=false $V/bin/reflex db migrate > $W/logs/tw-up-migrate.log 2>&1; echo "migrate after upgrade rc=$?")
echo "### tw up $(date +%T)"; $W/bin/run_app.sh $A $V $FP $BP $W/logs/tw-up.server.log || exit 1
pkgsnap $A tw-up; diff $W/pkg/tw-base.web.package.json $W/pkg/tw-up.web.package.json > $W/pkg/tw-base-to-up.package.diff; echo "package.json diff: $(grep -E '^[<>]' $W/pkg/tw-base-to-up.package.diff | tr -s ' ' | tr '\n' ' ')"
QA_EXPECT_SESSION=0 $DRV $W/scripts/drive_twitter.py http://localhost:$FP/ $S tw-up up $T 0.10.0a3 | summ
$W/bin/stop_app.sh $A $FP $BP
$SB/envs/driver/bin/python $W/scripts/dbdump.py $A/reflex.db > $W/logs/tw-db-up.txt
echo "### tw cold $(date +%T)"; rm -rf $A/.web; $W/bin/run_app.sh $A $V $FP $BP $W/logs/tw-cold.server.log || exit 1
pkgsnap $A tw-cold; diff -q $W/pkg/tw-up.web.package.json $W/pkg/tw-cold.web.package.json && echo "cold package.json == up"
QA_USER_SUFFIX=c $DRV $W/scripts/drive_twitter.py http://localhost:$FP/ $S tw-cold-base base $W/ctl/tw-cold.tok 0.10.0a3 | summ
$W/bin/stop_app.sh $A $FP $BP
for t in base up cold; do echo "--- tw-$t server-log warnings:"; logscan $W/logs/tw-$t.server.log; done
echo "### tw done $(date +%T)"
