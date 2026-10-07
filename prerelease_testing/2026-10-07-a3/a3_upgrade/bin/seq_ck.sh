#!/usr/bin/env bash
# clock: 0.9.12 baseline -> ONE browser context kept open across stop -> in-place upgrade -> restart (clock_session.py) -> a3 -> cold.
set -u; . $(dirname $0)/common.sh
A=$W/clock; V=$SB/envs/a3_upgrade-ck; FP=3226; BP=8226; S=$W/shots/ck; C=$W/ctl/ck
rm -rf $A/.web $A/reflex.lock $A/.states $C; mkdir -p $S $C
echo "### ck base $(date +%T)"; $W/bin/run_app.sh $A $V $FP $BP $W/logs/ck-base.server.log || exit 1
$DRV $W/scripts/drive_clock.py http://localhost:$FP/ $S ck-base | summ
pkgsnap $A ck-base
$DRV $W/scripts/clock_session.py http://localhost:$FP/ $S ck-session-up-a3 $C > $W/logs/ck-session.driver.log 2>&1 & SESS=$!
for i in $(seq 1 120); do [ -f $C/ready ] && break; sleep 1; done; echo "session ready: $([ -f $C/ready ] && echo yes || echo NO)"
$W/bin/stop_app.sh $A $FP $BP; touch $C/down
echo "### ck upgrade $(date +%T)"; upgrade ck ck 'reflex==0.10.0a3' 'pydantic<2.14'
echo "### ck up $(date +%T)"; $W/bin/run_app.sh $A $V $FP $BP $W/logs/ck-up.server.log || exit 1
touch $C/up; for i in $(seq 1 240); do [ -f $C/done ] && break; sleep 1; done; wait $SESS; summ < $W/logs/ck-session.driver.log
pkgsnap $A ck-up; diff $W/pkg/ck-base.web.package.json $W/pkg/ck-up.web.package.json > $W/pkg/ck-base-to-up.package.diff; echo "package.json diff: $(grep -E '^[<>]' $W/pkg/ck-base-to-up.package.diff | tr -s ' ' | tr '\n' ' ')"
$DRV $W/scripts/drive_clock.py http://localhost:$FP/ $S ck-up | summ
$W/bin/stop_app.sh $A $FP $BP
echo "### ck cold $(date +%T)"; rm -rf $A/.web; $W/bin/run_app.sh $A $V $FP $BP $W/logs/ck-cold.server.log || exit 1
pkgsnap $A ck-cold; diff -q $W/pkg/ck-up.web.package.json $W/pkg/ck-cold.web.package.json && echo "cold package.json == up"
$DRV $W/scripts/drive_clock.py http://localhost:$FP/ $S ck-cold | summ
$W/bin/stop_app.sh $A $FP $BP
for t in base up cold; do echo "--- ck-$t server-log warnings:"; logscan $W/logs/ck-$t.server.log; done
echo "### ck done $(date +%T)"
