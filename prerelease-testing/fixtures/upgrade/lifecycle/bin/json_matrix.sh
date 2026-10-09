#!/usr/bin/env bash
# #7428 / A3-07 / A3-08 matrix: scripts/json_drain.py runs against a fresh copy of apps/jsondrain, one server at a time.
# Usage: json_matrix.sh <label> <venv-name> "<sig>:<rate> ..."   sig: INT-group | INT-pid | TERM-pid ; rate = lines/s the slow reader consumes
# Env: FP/BP (3510/8510), QA_NOJSON=1 drops --json, QA_CHATTY_OFF=1 disables the printer, QA_EOF_CAP / QA_WAIT_CAP shorten the hang cases.
# Expected on 0.10.0a3..a5 (unchanged since): INT-group:40 and TERM-pid:40 exit ~6-7 s rc 0, 0 lost / 0 invalid; TERM-pid:6 exits at the 30 s
# wall cap with a truncated last record (A3-08); INT-pid never exits (A3-07, killed at the cap; also with QA_CHATTY_OFF=1).
set -u; . "$(dirname "$0")/../../bin/env.sh"; L=$(cd "$(dirname "$0")/.." && pwd); FP=${FP:-3510}; BP=${BP:-8510}
lbl=$1; venv=$2; shift 2
mkdir -p "$L/out/jsondrain" "$L/run"; A=$L/run/jsondrain-$lbl
for spec in $*; do
  sig=${spec%%:*}; rate=${spec##*:}
  rm -rf "$A"; cp -r "$L/apps/jsondrain" "$A"
  echo "### $lbl $sig rate=$rate $(date +%T)"
  (cd "$SB" && "$DPY" "$L/scripts/json_drain.py" "$SB/envs/$venv" "$A" $FP $BP $sig $rate "$L/out/jsondrain/$lbl-$sig-r$rate.json" 2>&1 | tail -2)
  "$L/../bin/ports.sh" $FP $BP
done
