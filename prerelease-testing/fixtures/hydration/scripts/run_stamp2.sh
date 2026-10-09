#!/bin/bash
# Usage: run_stamp2.sh <venv> <dev|prod> <FP> <BP> <runs_stamp> <runs_same> <NTABS> [ENV=VAL...]
#   one server start of src/syncstamp; stamp_storm.py on /stamp (A3-12 original repro) then the /same control.
. "$(dirname "$0")/env.sh"
V=$1; MODE=$2; FP=$3; BP=$4; NS=$5; NC=$6; NT=$7; shift 7
O=$W/results/stamp; mkdir -p $O; cd $O
$F/scripts/srv.sh start ss-$V-$MODE $V $MODE $F/src/syncstamp $FP $BP "$@" > /dev/null || exit 1
$NP $DRV $F/drivers/waitsrv.py 500 http://localhost:$FP/ http://localhost:$BP/ping > /dev/null || { echo "server not up"; $F/scripts/srv.sh stop ss-$V-$MODE; exit 1; }
sleep 4
echo "state.js md5: $(md5sum < $W/run/ss-$V-$MODE/.web/utils/state.js | cut -c1-8)"
for P in /stamp /same; do
  N=$NS; [ $P = /same ] && N=$NC
  tag=$(echo $P | tr -d /)
  for i in $(seq 1 $N); do
    echo -n "$V $MODE $P n=$NT run $i: "
    $NP timeout 200 $DRV $F/drivers/stamp_storm.py http://localhost:$FP $P $NT stamp_${V}_${MODE}_${tag}_${NT}_$i.json 10 2>&1 | tail -1 | cut -c1-600
  done
done
$F/scripts/srv.sh stop ss-$V-$MODE > /dev/null
