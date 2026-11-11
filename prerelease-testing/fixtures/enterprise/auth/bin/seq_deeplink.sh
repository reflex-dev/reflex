#!/usr/bin/env bash
# reflex#7360 enterprise router probe (vauthd app + drivers/deeplink.py + audit page_load routes) on <venv> <label>:
# dev + Redis (3 reps), prod + Redis 1 worker (2 reps). Ports: dev 3620/8620, prod 8621, Redis 8629, mock IdP 8638.
# Usage: seq_deeplink.sh [venv] [label] [modes=dev,prod]
. "$(dirname "$0")/../../lib.sh"; fx_sync auth; E=$WORK/auth; B=$FX/auth/bin
V=${1:-$ENT_NEW}; L=${2:-new}; MODES=${3:-dev,prod}
DRV="$NP timeout 900 $DRVPY"
fx_app auth vauthd vauthd_$L
"$B/infra.sh" start
run_mode() {  # <tag> <base> <reps> <dev|prod>
  local tag=$1 base=$2 reps=$3 mode=$4
  redis-cli -p 8629 flushall
  rm -f "$E/logs/$L-$tag.audit.jsonl"
  VAUTHD_AUDIT_FILE=$E/logs/$L-$tag.audit.jsonl "$B/start_app.sh" "$V" vauthd_$L $mode "$E/logs/$L-$tag.server.log"; head -1 "$E/logs/$L-$tag.server.log"
  "$B/wait_ready.sh" $base/ $base 600 && (cd "$E/drivers" && $DRV deeplink.py $base $L-$tag $reps 2>&1 | tail -n 4 | cut -c1-600)
  "$B/stop_app.sh"
  echo "server log $L-$tag: tracebacks=$(grep -c Traceback "$E/logs/$L-$tag.server.log") deprecate=$(grep -ci 'deprecat' "$E/logs/$L-$tag.server.log")"
  "$DRVPY" -I "$E/drivers/audit_routes.py" "$E/logs/$L-$tag.audit.jsonl"
}
[[ $MODES == *dev* ]] && run_mode dl-dev-redis http://localhost:3620 3 dev
[[ $MODES == *prod* ]] && GRANIAN_WORKERS=1 run_mode dl-prod-redis-1w http://localhost:8621 2 prod
"$B/infra.sh" stop
echo "### deeplink $L done $(date +%T)"
