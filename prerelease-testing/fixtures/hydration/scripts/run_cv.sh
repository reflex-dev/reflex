#!/bin/bash
# Usage: run_cv.sh <venv> <dev|prod> <label> <FP> <BP> <variants|all> [ENV=VAL...]  -- cvstore + drive_cvstore.py (+ drive_cvnav.py when NAV=1)
#   F-003 (computed var rewriting a storage var at hydration must reach the browser), variants a-j (space-separated, quoted).
#   Prints a diff of the summary against expected/cvstore_<dev|prod>.summary.txt (0.10.0a5 = 0.10.0, seed-independent)
#   for "all"; set EXPECT=<file> to compare with another file (e.g. expected/cvstore_ctrl_a1_dev_abg.summary.txt for the
#   0.10.0a1 positive control run with variants "a b g").
. "$(dirname "$0")/env.sh"
V=$1; MODE=$2; L=$3; FP=$4; BP=$5; VARS=$6; shift 6
O=$W/results/f003; mkdir -p $O/frames
[ "$VARS" = all ] && VARS=""
$F/scripts/srv.sh start cv-$L $V $MODE $F/src/cvstore $FP $BP "$@" > /dev/null || exit 1
$NP $DRV $F/drivers/waitsrv.py 400 http://localhost:$FP/ http://localhost:$BP/ping > /dev/null || { $F/scripts/srv.sh stop cv-$L; exit 1; }
sleep 3
cd $W
$NP timeout 900 $DRV $F/cv/drivers/drive_cvstore.py http://localhost:$FP $O/frames $L $VARS > $O/$L.summary.txt 2>&1
grep -E "SUMMARY|FAIL|PASS" $O/$L.summary.txt | cut -c1-260
EXP=${EXPECT:-}; [ -z "$EXP" ] && [ -z "$VARS" ] && EXP=$F/expected/cvstore_$MODE.summary.txt
if [ -n "$EXP" ]; then
  if sed "s/^SUMMARY $L /SUMMARY LABEL /" $O/$L.summary.txt | diff "$EXP" - > $O/$L.expected.diff; then echo "CVSTORE MATCHES $(basename "$EXP")"
  else echo "CVSTORE DIFFERS from $(basename "$EXP") ($(grep -c '^[<>]' $O/$L.expected.diff) lines, $O/$L.expected.diff):"; head -20 $O/$L.expected.diff | cut -c1-220; fi
fi
if [ "${NAV:-0}" = 1 ]; then $NP timeout 600 $DRV $F/cv/drivers/drive_cvnav.py http://localhost:$FP $L > $O/$L.cvnav.txt 2>&1; tail -12 $O/$L.cvnav.txt | cut -c1-200; fi
$F/scripts/srv.sh stop cv-$L > /dev/null
