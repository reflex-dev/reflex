#!/usr/bin/env bash
# Usage: seq_misc.sh <app> <frontend_port> <backend_port>
# Full upgrade sequence for one small app: 0.9.12 baseline -> in-place upgrade -> rerun -> cold rerun.
set -u
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/upgrades_a; APP=$1; FP=$2; BP=$3; A=$W/$APP; V=$SB/envs/upgrades_a-$APP
DRV="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 timeout 600 $SB/envs/driver/bin/python $W/scripts/drive_misc.py"
summ() { grep -E '^\[(FAIL|ANOMALY)|^==|UNEXPECTED|PAGE ERROR|BAD REQ' | cut -c1-220; }
echo "### $APP base"; $W/bin/run_app.sh $A $V $FP $BP $W/logs/$APP-base.server.log || exit 1
(cd $W && $DRV $APP http://localhost:$FP/ $W/shots/$APP $APP-base | summ)
cp $A/.web/package.json $W/pkg/$APP-base.web.package.json; (ls -la --time-style=+%T $A/reflex.lock; sha256sum $A/reflex.lock/*) > $W/pkg/$APP-base.reflex.lock.ls
$W/bin/stop_app.sh $A $FP $BP
echo "### $APP upgrade"; (cd $SB && uv --no-config pip install --python $V/bin/python --prerelease=allow -U 'reflex==0.10.0a1' 2>&1 | grep -v UV_NATIVE > $W/logs/$APP-upgrade.install.log)
(cd $SB && uv --no-config pip freeze --python $V/bin/python 2>/dev/null > $W/freeze/$APP-up.txt); diff $W/freeze/$APP-base.txt $W/freeze/$APP-up.txt > $W/freeze/$APP-base-to-up.diff; grep -cE '^>' $W/freeze/$APP-base-to-up.diff
echo "### $APP up"; $W/bin/run_app.sh $A $V $FP $BP $W/logs/$APP-up.server.log || exit 1
cp $A/.web/package.json $W/pkg/$APP-up.web.package.json; diff $W/pkg/$APP-base.web.package.json $W/pkg/$APP-up.web.package.json > $W/pkg/$APP-base-to-up.package.diff; grep -E '^[<>]' $W/pkg/$APP-base-to-up.package.diff | tr '\n' ' '; echo
(cd $W && $DRV $APP http://localhost:$FP/ $W/shots/$APP $APP-up | summ)
$W/bin/stop_app.sh $A $FP $BP
echo "### $APP cold"; rm -rf $A/.web; $W/bin/run_app.sh $A $V $FP $BP $W/logs/$APP-cold.server.log || exit 1
cp $A/.web/package.json $W/pkg/$APP-cold.web.package.json; diff -q $W/pkg/$APP-up.web.package.json $W/pkg/$APP-cold.web.package.json && echo "cold package.json == up"
(cd $W && $DRV $APP http://localhost:$FP/ $W/shots/$APP $APP-cold | summ)
$W/bin/stop_app.sh $A $FP $BP
for t in base up cold; do echo "--- $APP-$t server-log warnings:"; grep -iE 'warn|error|traceback|exception|deprecat' $W/logs/$APP-$t.server.log | grep -v -E 'incorrect peer|redis_lock_warning|react-error-boundary|errorBoundaries|SitemapPlugin' | cut -c1-200 | sort | uniq -c | head -8; done
