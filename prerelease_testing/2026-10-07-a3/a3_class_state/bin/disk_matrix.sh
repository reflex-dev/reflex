#!/bin/bash
# N-004 disk store matrix: for each (writer, reader) pair, writer saves a session into a fresh shared dir, reader loads it.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a3_class_state
OUT=$1; shift; export REFLEX_TELEMETRY_ENABLED=false
cd $W/probes/disk || exit 1
{
for w in "$@"; do for r in "$@"; do
  D=$W/run/disk/$w-$r; rm -rf $D; mkdir -p $D
  echo "== writer=$w reader=$r"
  REFLEX_STATES_WORKDIR=$D $SB/envs/$w/bin/python -I disk_probe.py $w save tok-$w-$r 2>&1 | tail -n 2
  REFLEX_STATES_WORKDIR=$D $SB/envs/$r/bin/python -I disk_probe.py $r step tok-$w-$r 2>&1 | tail -n 2
  REFLEX_STATES_WORKDIR=$D $SB/envs/$w/bin/python -I disk_probe.py $w load tok-$w-$r 2>&1 | tail -n 2
done; done
} > $OUT 2>&1; cat $OUT
