#!/bin/bash
# Usage: vraw.sh <tag> <runs> <FP> <ntabs> <stagger_ms> <click_id> <click_after_ms> [observe_s=10]
#   stock headful Chromium under Xvfb, real background tabs (drivers/vh_rawcdp.py) -> out/<tag>_<i>.json
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; V=$SB/apps/verify_hydration
TAG=$1; N=$2; FP=$3; NT=$4; ST=$5; CL=$6; CA=$7; OBS=${8:-10}
mkdir -p $V/out; cd $V/out
for i in $(seq 1 $N); do
  echo -n "$TAG #$i: "
  env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 VH_TMP=$V/run timeout -k 5 150 xvfb-run -a -s "-screen 0 1280x900x24" \
    $SB/envs/driver/bin/python $V/drivers/vh_rawcdp.py http://localhost:$FP ${TAG}_$i.json $NT $ST $CL $CA $OBS > ${TAG}_$i.stdout 2>&1
  tail -1 ${TAG}_$i.stdout | cut -c1-500
  sleep 1
done
