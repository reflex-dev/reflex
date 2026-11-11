#!/bin/bash
# Usage: vraw.sh <tag> <runs> <FP> <ntabs> <stagger_ms> <click_id|docs> <click_after_ms> [observe_s=10]
#   stock headful Chromium under Xvfb, REAL background tabs (vh/drivers/vh_rawcdp.py, CDP port 8670) -> $W/results/vh/<tag>_<i>.json
. "$(dirname "$0")/../../scripts/env.sh"
TAG=$1; N=$2; FP=$3; NT=$4; ST=$5; CL=$6; CA=$7; OBS=${8:-10}
O=$W/results/vh; mkdir -p "$O"; cd "$O" || exit 1
for i in $(seq 1 "$N"); do
  echo -n "$TAG #$i: "
  $NP VH_TMP="$W/run" timeout -k 5 150 xvfb-run -a -s "-screen 0 1280x900x24" \
    "$DRV" "$F/vh/drivers/vh_rawcdp.py" "http://localhost:$FP" "${TAG}_$i.json" "$NT" "$ST" "$CL" "$CA" "$OBS" > "${TAG}_$i.stdout" 2>&1
  tail -1 "${TAG}_$i.stdout" | cut -c1-500
  sleep 1
done
