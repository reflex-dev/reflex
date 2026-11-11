#!/usr/bin/env bash
# fullstack_chain.sh: full-stack prod (one port, frontend built + mounted) on prev then new, sequentially.
set -u; : "${SB:?}"; V=$SB/apps/verify_pm1; cd "$V" || exit 2
export REFLEX_REDIS_URL=redis://localhost:8739 REFLEX_TELEMETRY_ENABLED=false
for v in prev new; do
  echo "#### $v full-stack prod 8720 $(date +%T)"
  ./scripts/probe_run.sh "$v" "$v-prod-full" prod 8720
  echo "index: $(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' --max-time 5 http://localhost:8720/ || true) (after stop, expect 000)"
done
echo "#### done $(date +%T)"
