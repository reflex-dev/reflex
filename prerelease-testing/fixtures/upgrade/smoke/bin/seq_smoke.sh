#!/usr/bin/env bash
# Blank-app smoke: `reflex init --template blank` + dev + prod (/ping, /sitemap.xml, colour-mode toggle survives reload, no console
# errors / failed requests) per venv. Usage: seq_smoke.sh [venv ...] (default $NEW; e.g. fresh py3.11 / py3.14 venvs from
# inst/bin/n001.sh). Ports FP/BP (3516/8516). Generated .web/package.json copied to smoke/out/<venv>.web.package.json for a cross-venv diff.
set -u; . "$(dirname "$0")/../../bin/env.sh"; M=$(cd "$(dirname "$0")/.." && pwd); U=$M/../up
FP=${FP:-3516}; BP=${BP:-8516}; S=$M/out; mkdir -p "$S" "$M/logs"
summ() { grep -E '^\[(FAIL|ANOMALY)|^== |UNEXPECTED|PAGE ERROR|BAD REQ' | cut -c1-260; }
for v in ${@:-$NEW}; do
  V=$SB/envs/$v; A=$M/run/$v/app; rm -rf "$M/run/$v"; mkdir -p "$A"
  echo "### $v init $(date +%T)"; (cd "$A" && "$V/bin/reflex" init --template blank > "$M/logs/smoke-$v-init.log" 2>&1; echo "init rc=$? $(grep -c npmmirror "$M/logs/smoke-$v-init.log") npmmirror lines; requirements: $(tr '\n' ' ' < requirements.txt)")
  "$U/bin/run_app.sh" "$A" "$V" $FP $BP "$M/logs/smoke-$v-dev.server.log" || continue
  $DRV "$U/scripts/drive_smoke.py" http://localhost:$FP "$S" smoke-$v-dev | summ
  "$U/bin/stop_app.sh" "$A" $FP $BP
  REFLEX_API_URL=http://localhost:$FP "$U/bin/run_app.sh" "$A" "$V" $FP $FP "$M/logs/smoke-$v-prod.server.log" --env prod || continue
  for r in /ping /sitemap.xml /nope; do echo "prod $r -> $(http_code http://localhost:$FP$r)"; done
  $DRV "$U/scripts/drive_smoke.py" http://localhost:$FP "$S" smoke-$v-prod | summ
  "$U/bin/stop_app.sh" "$A" $FP
  for t in dev prod; do echo "--- smoke-$v-$t server-log errors: $(grep -ciE 'error|traceback' "$M/logs/smoke-$v-$t.server.log")"; done
  cp "$A/.web/package.json" "$S/$v.web.package.json"
done
echo "### smoke done $(date +%T)"
