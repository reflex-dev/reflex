#!/bin/bash
# Usage: vrun.sh <tag> <runs> <FP> <scenario> <ntabs> [driver options...]  -> out/<tag>_<i>.json, one summary line per run
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; V=$SB/apps/verify_hydration
TAG=$1; N=$2; FP=$3; SC=$4; NT=$5; shift 5
mkdir -p $V/out; cd $V/out
for i in $(seq 1 $N); do
  echo -n "$TAG #$i: "
  env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 VH_TMP=$V/run timeout -k 5 150 $SB/envs/driver/bin/python $V/drivers/vh_tabs.py http://localhost:$FP ${TAG}_$i.json $SC $NT "$@" > ${TAG}_$i.stdout 2>&1; tail -1 ${TAG}_$i.stdout | cut -c1-700
  sleep 1
done
