#!/usr/bin/env bash
# reflex init --template blank + dev + prod smoke on Python 3.11 / 3.14 (venvs a3_upgrade-py311 / -py314).
set -u; . $(dirname $0)/common.sh
for k in py311 py314; do
  V=$SB/envs/a3_upgrade-$k; A=$W/smoke$k/app; FP=3236; BP=8236; S=$W/shots/smoke
  rm -rf $W/smoke$k; mkdir -p $A $S
  echo "### $k init $(date +%T)"; (cd $A && REFLEX_TELEMETRY_ENABLED=false $V/bin/reflex init --template blank > $W/logs/smoke-$k-init.log 2>&1; echo "init rc=$? $(grep -c npmmirror $W/logs/smoke-$k-init.log) npmmirror lines")
  cat $A/requirements.txt
  $W/bin/run_app.sh $A $V $FP $BP $W/logs/smoke-$k-dev.server.log || continue
  $DRV $W/scripts/drive_smoke.py http://localhost:$FP $S smoke-$k-dev | summ
  $W/bin/stop_app.sh $A $FP $BP
  REFLEX_API_URL=http://localhost:$FP $W/bin/run_app.sh $A $V $FP $FP $W/logs/smoke-$k-prod.server.log --env prod || continue
  for r in /ping /sitemap.xml; do echo "prod $r -> $(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' http://localhost:$FP$r)"; done
  $DRV $W/scripts/drive_smoke.py http://localhost:$FP $S smoke-$k-prod | summ
  $W/bin/stop_app.sh $A $FP
  for t in dev prod; do echo "--- smoke-$k-$t server-log warnings:"; logscan $W/logs/smoke-$k-$t.server.log; done
  cp $A/.web/package.json $W/pkg/smoke-$k.web.package.json
done
diff $W/pkg/smoke-py311.web.package.json $W/pkg/smoke-py314.web.package.json && echo "py311 package.json == py314"
echo "### smoke done $(date +%T)"
