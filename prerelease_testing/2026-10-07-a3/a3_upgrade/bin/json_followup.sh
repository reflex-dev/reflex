#!/usr/bin/env bash
# SIGINT-to-pid controls: 0.9.12 --json (no supervisor) and a3/a2 without --json; short caps so a hang costs ~60 s.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a3_upgrade
until grep -q '^### a2 INT-pid' $W/logs/jsondrain-matrix.txt && [ $(grep -c '^{' $W/logs/jsondrain-matrix.txt) -ge 8 ]; do sleep 3; done
export QA_EOF_CAP=40 QA_WAIT_CAP=20
$W/bin/json_matrix.sh s912 stable INT-pid:40 INT-group:40 TERM-pid:40
QA_NOJSON=1 $W/bin/json_matrix.sh a3plain a3 INT-pid:40
QA_NOJSON=1 $W/bin/json_matrix.sh a2plain alpha2 INT-pid:40
echo "### followup done $(date +%T)"
