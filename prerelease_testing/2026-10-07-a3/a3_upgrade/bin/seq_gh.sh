#!/usr/bin/env bash
# github-stats: 0.9.12 baseline (fresh profile) -> in-place upgrade -> persist (same profile) -> prod -> cold.
set -u; . $(dirname $0)/common.sh
A=$W/github-stats; V=$SB/envs/a3_upgrade-gh; FP=3224; BP=8224; STUBP=8228; P=$W/profiles/gh; S=$W/shots/gh; STUB=http://127.0.0.1:$STUBP
export QA_GITHUB_GRAPHQL_URL=$STUB/graphql GITHUB_API_TOKEN=qa-dummy-token
rm -rf $A/.web $A/reflex.lock $A/.states $P $W/profiles/gh-cold; mkdir -p $S
$SB/envs/driver/bin/python $W/scripts/github_stub.py $STUBP > $W/logs/gh-stub.log 2>&1 & STUBPID=$!; sleep 1
echo "### gh base $(date +%T)"; $W/bin/run_app.sh $A $V $FP $BP $W/logs/gh-base.server.log || { kill $STUBPID; exit 1; }
$DRV $W/scripts/drive_github_stats.py http://localhost:$FP/ $S gh-base fresh $P $STUB | summ
pkgsnap $A gh-base; $W/bin/stop_app.sh $A $FP $BP
echo "### gh upgrade $(date +%T)"; upgrade gh gh 'reflex==0.10.0a3' 'pydantic<2.14'
echo "### gh up $(date +%T)"; $W/bin/run_app.sh $A $V $FP $BP $W/logs/gh-up.server.log || { kill $STUBPID; exit 1; }
pkgsnap $A gh-up; diff $W/pkg/gh-base.web.package.json $W/pkg/gh-up.web.package.json > $W/pkg/gh-base-to-up.package.diff; echo "package.json diff: $(grep -E '^[<>]' $W/pkg/gh-base-to-up.package.diff | tr -s ' ' | tr '\n' ' ')"
$DRV $W/scripts/storage_probe.py http://localhost:$FP $S gh-up-firstload-home $P --wait 8 --expect-text "Alice" --forbid-writes | grep -E "^(PASS|FAIL)|CHANGING|idempotent write"
$DRV $W/scripts/drive_github_stats.py http://localhost:$FP/ $S gh-up persist $P $STUB | summ
$W/bin/stop_app.sh $A $FP $BP
echo "### gh prod $(date +%T)"; REFLEX_API_URL=http://localhost:$FP $W/bin/run_app.sh $A $V $FP $FP $W/logs/gh-up-prod.server.log --env prod || { kill $STUBPID; exit 1; }
$DRV $W/scripts/drive_github_stats.py http://localhost:$FP/ $S gh-up-prod persist $P $STUB | summ
$W/bin/stop_app.sh $A $FP
echo "### gh cold $(date +%T)"; rm -rf $A/.web; $W/bin/run_app.sh $A $V $FP $BP $W/logs/gh-cold.server.log || { kill $STUBPID; exit 1; }
pkgsnap $A gh-cold; diff -q $W/pkg/gh-up.web.package.json $W/pkg/gh-cold.web.package.json && echo "cold package.json == up"
$DRV $W/scripts/drive_github_stats.py http://localhost:$FP/ $S gh-cold fresh $W/profiles/gh-cold $STUB | summ
$W/bin/stop_app.sh $A $FP $BP; kill $STUBPID
for t in base up up-prod cold; do echo "--- gh-$t server-log warnings:"; logscan $W/logs/gh-$t.server.log; done
echo "### gh done $(date +%T)"
