#!/usr/bin/env bash
# Upgrade-guide e2e app (app/guideapp: /sample = guide sample 1 verbatim, /portable = get_fields() recipe, /bg = section 3
# Parent/Child verbatim + variants, /defaults = runtime class assignment seen by N fresh sessions) driven by scripts/drive_guide.py.
# Usage: seq_guide.sh [venv ...]  dev runs per venv (default "$NEW $PREV"), then $NEW prod + Redis (2*cpu+1 workers). Ports FP/BP (3514/8514), Redis RP (8509).
set -u; . "$(dirname "$0")/../../bin/env.sh"; G=$(cd "$(dirname "$0")/.." && pwd); U=$G/../up
A=$G/run/app; FP=${FP:-3514}; BP=${BP:-8514}; RP=${RP:-8509}; S=$G/out; mkdir -p "$S" "$G/logs" "$G/run"
summ() { grep -v '^\[PASS'; }
for v in ${@:-$NEW $PREV}; do
  rm -rf "$A"; cp -r "$G/app" "$A"
  echo "### guide $v dev $(date +%T)"; "$U/bin/run_app.sh" "$A" "$SB/envs/$v" $FP $BP "$G/logs/guide-$v-dev.server.log" || continue
  $DRV "$U/scripts/drive_guide.py" http://localhost:$FP "$S" guide-$v-dev --defaults-tabs 2 | summ
  "$U/bin/stop_app.sh" "$A" $FP $BP
done
[ "${SKIP_PROD:-0}" = 1 ] && exit 0
echo "### guide $NEW prod+redis $(date +%T)"; rm -rf "$A"; cp -r "$G/app" "$A"
setsid redis-server --port $RP --bind 127.0.0.1 --save '' --appendonly no > "$G/logs/guide-redis.log" 2>&1 < /dev/null & RPID=$!; sleep 1
REFLEX_REDIS_URL=redis://localhost:$RP REFLEX_API_URL=http://localhost:$FP "$U/bin/run_app.sh" "$A" "$SB/envs/$NEW" $FP $FP "$G/logs/guide-$NEW-prod.server.log" --env prod && {
  echo "granian workers spawned: $(grep -c 'Spawning worker-' "$G/logs/guide-$NEW-prod.server.log")"
  $DRV "$U/scripts/drive_guide.py" http://localhost:$FP "$S" guide-$NEW-prod --defaults-tabs 8 | summ
  "$U/bin/stop_app.sh" "$A" $FP; }
redis-cli -p $RP shutdown nosave >/dev/null 2>&1; kill $RPID 2>/dev/null
echo "### guide done $(date +%T)"
