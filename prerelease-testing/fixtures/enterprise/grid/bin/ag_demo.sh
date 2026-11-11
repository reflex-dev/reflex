#!/usr/bin/env bash
# AG Grid demo (+ QA pages) smoke / features / model / state-coldefs probe. Needs bin/fetch_demos.sh and a demo venv with
# faker/pandas/aiosqlite (bin/build_demo_venv.sh). Usage: ag_demo.sh <venv> <prod|dev> <label>   (prod 3606; dev 3607/8607)
set -u
. "$(dirname "$0")/../../lib.sh"; fx_sync grid; W=$WORK/grid; B=$FX/grid/bin
V=$1; M=$2; L=$3
[ -d "$W/demos/ag_grid" ] || { echo "run bin/fetch_demos.sh first"; exit 1; }
R=$W/runs/ag_grid_demo_${V//-/}; mkdir -p "$R"
(cd "$W/demos/ag_grid" && tar --exclude=.web --exclude=__pycache__ -cf - .) | (cd "$R" && tar -xf -)
(cd "$R" && rm -f reflex.db && CI=true REFLEX_TELEMETRY_ENABLED=false REFLEX_DB_URL=sqlite:///reflex.db "$SB/envs/$V/bin/reflex" db migrate > "$W/logs/ag_grid-migrate-$L.log" 2>&1)
if [ "$M" = prod ]; then FP=3606; BP=3606; else FP=3607; BP=8607; fi
"$B/start.sh" "$V" "$R" "$W/logs/ag_grid-$M-$L.log" "$M" $FP $BP REFLEX_DB_URL=sqlite:///reflex.db || { "$B/stop.sh"; exit 1; }
cd "$W"; U=http://localhost:$FP; O=out/ag_${M}_$L
ROUTES="/ /advanced-serialization /aligned-grids /cell-selection /editable /fill-handle /formatters /integrated-charts /master-detail /model /model-auth /model-ssrm /pivot /qa-grid-memo /qa-grid-props /qa-model-workaround /selected-items /simple-serialization /state-grid /tree"
$NP "$DRVPY" scripts/smoke_routes.py $U $O ag_grid-smoke "$V" $ROUTES > $O-smoke.txt 2>&1
$NP "$DRVPY" scripts/probe_state_coldefs.py $U $O "$V" $M-$L > $O-coldefs.txt 2>&1
$NP "$DRVPY" scripts/drive_ag_features.py $U $O "$V" > $O-features.txt 2>&1
$NP "$DRVPY" scripts/drive_ag_model.py $U $O "$V" "$R/reflex.db" > $O-model.txt 2>&1
for k in smoke coldefs features model; do echo "$k: $(grep -c '^\[PASS\]' $O-$k.txt) pass / $(grep -c '^\[FAIL\]' $O-$k.txt) fail"; grep '^\[FAIL\]' $O-$k.txt | cut -c1-200; done
echo "server tracebacks: $(grep -c Traceback "$W/logs/ag_grid-$M-$L.log")"
"$B/stop.sh"
