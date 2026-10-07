#!/usr/bin/env bash
# SIGINT/SIGTERM to the pid with a FAST consumer and no chatty output (isolates the supervisor from pipe back-pressure).
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a3_upgrade
export QA_EOF_CAP=40 QA_WAIT_CAP=20 QA_CHATTY_OFF=1
$W/bin/seq_guide2.sh > $W/logs/seq-guide2.txt 2>&1
$W/bin/json_matrix.sh a3fast a3 INT-pid:100000 TERM-pid:100000
$W/bin/json_matrix.sh a2fast alpha2 INT-pid:100000
$W/bin/json_matrix.sh s912fast stable INT-pid:100000 TERM-pid:100000
QA_NOJSON=1 $W/bin/json_matrix.sh s912plainfast stable INT-pid:100000
echo "### json2 done $(date +%T)"
