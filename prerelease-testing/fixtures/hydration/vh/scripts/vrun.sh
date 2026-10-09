#!/bin/bash
# Usage: vrun.sh <tag> <runs> <FP> <scenario> <ntabs> [driver options...]  -> $W/results/vh/<tag>_<i>.json, one summary line per run
#   Playwright multi-tab driver vh/drivers/vh_tabs.py (scenarios: restore, docs, docs-restart, open, ...; see its --help).
. "$(dirname "$0")/../../scripts/env.sh"
TAG=$1; N=$2; FP=$3; SC=$4; NT=$5; shift 5
O=$W/results/vh; mkdir -p "$O"; cd "$O" || exit 1
for i in $(seq 1 "$N"); do
  echo -n "$TAG #$i: "
  $NP VH_TMP="$W/run" timeout -k 5 150 "$DRV" "$F/vh/drivers/vh_tabs.py" "http://localhost:$FP" "${TAG}_$i.json" "$SC" "$NT" "$@" > "${TAG}_$i.stdout" 2>&1
  tail -1 "${TAG}_$i.stdout" | cut -c1-700
  sleep 1
done
