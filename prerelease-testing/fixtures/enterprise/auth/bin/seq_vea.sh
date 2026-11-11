#!/usr/bin/env bash
# A3-10 / A3-09 verifier (vea app + drivers/vea_drv.py), dev unless MODE=prod. Usage: seq_vea.sh [venv] [label] [scenarios] [reps]
# scenarios: storx,xsync (A3-10) and stale,away,live,stalenav (A3-09). Env: MGR=redis|disk|memory (default redis),
# VEA_INSTRUMENT=1 (logs VEA_FILTER lines: which deltas enterprise's filter rewrote), VEA_FIX=1 (causality counter-experiment),
# MODE=prod (single port 8621; GRANIAN_WORKERS passes through).
. "$(dirname "$0")/../../lib.sh"; fx_sync auth; E=$WORK/auth; B=$FX/auth/bin
V=${1:-$ENT_NEW}; L=${2:-new}; SCEN=${3:-storx,xsync,stale,away}; REPS=${4:-2}; MODE=${MODE:-dev}
TAG=$L-$MODE-${MGR:-redis}; BASE=$([ "$MODE" = prod ] && echo http://localhost:8621 || echo http://localhost:3620)
fx_app auth vea vea_$L
"$B/infra.sh" start; redis-cli -p 8629 flushall
OIDC_CLIENT=vea-client "$B/start_app.sh" "$V" vea_$L $MODE "$E/logs/$TAG-vea.server.log"
"$B/wait_ready.sh" $BASE/ $BASE 600 || { "$B/stop_app.sh"; "$B/infra.sh" stop; exit 1; }
for s in ${SCEN//,/ }; do
  (cd "$E/drivers" && $NP timeout 900 "$DRVPY" vea_drv.py $s $BASE $TAG $REPS 2>&1 | tail -n 3 | cut -c1-400)
done
(cd "$E/drivers" && for s in stale away live; do [ -f ../out/$TAG-$s.json ] && $DRVPY vea_summ.py ../out/$TAG-$s.json; done) 2>&1 | cut -c1-300
"$B/stop_app.sh"; "$B/infra.sh" stop
echo "server log: tracebacks=$(grep -c Traceback "$E/logs/$TAG-vea.server.log") VEA_FILTER=$(grep -c VEA_FILTER "$E/logs/$TAG-vea.server.log")"
