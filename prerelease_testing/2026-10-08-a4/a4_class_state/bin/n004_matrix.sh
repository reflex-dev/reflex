#!/bin/bash
# N-004 a3 <-> a4 (and 0.9.12) interchange, Python level. Usage: bin/n004_matrix.sh <outdir> <venv>...
# (1) ORIGINAL derive_h_schema.py: save SchemaState with each venv (default 0), load every save with every venv at default 0 and 5.
# (2) StateManagerDisk: writer saves, reader steps (load+mutate+save), writer loads again (shared REFLEX_STATES_WORKDIR).
# (3) schema hashes of several state shapes (probes/schema_hashes.py).
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a4_class_state
OUT=$1; shift; mkdir -p $OUT; export REFLEX_TELEMETRY_ENABLED=false
rm -rf $W/run/schema $W/run/disk; mkdir -p $W/run/schema $W/run/disk; cp $W/orig/schema/*.py $W/run/schema/; cp $W/orig/disk/*.py $W/run/disk/
D=$W/run/schema/out; mkdir -p $D
( cd $W/run/schema
for s in "$@"; do
  echo "+ SCHEMA_DEFAULT=0 $s save"; SCHEMA_DEFAULT=0 $SB/envs/$s/bin/python derive_h_schema.py $s save $D/saved-$s.bin
  for l in "$@"; do for d in 0 5; do
    printf "saved=%-22s loader=%-22s d$d -> " "$s" "$l"; SCHEMA_DEFAULT=$d $SB/envs/$l/bin/python derive_h_schema.py $l load $D/saved-$s.bin
  done; done
done
echo "+ pickle contents"
for s in "$@"; do $SB/envs/driver/bin/python -I $W/orig/pickle_keys.py $D/saved-$s.bin; done ) > $OUT/schema_matrix.txt 2>&1
( cd $W/run/disk
for w in "$@"; do for r in "$@"; do
  DD=$W/run/disk/st-$w-$r; rm -rf $DD; mkdir -p $DD; T=tok-${w##*-}-${r##*-}  # client token must not contain "_"
  echo "== writer=$w reader=$r"
  REFLEX_STATES_WORKDIR=$DD $SB/envs/$w/bin/python -I disk_probe.py $w save $T 2>&1 | tail -n 1
  REFLEX_STATES_WORKDIR=$DD $SB/envs/$r/bin/python -I disk_probe.py $r step $T 2>&1 | tail -n 1
  REFLEX_STATES_WORKDIR=$DD $SB/envs/$w/bin/python -I disk_probe.py $w load $T 2>&1 | tail -n 1
done; done ) > $OUT/disk_matrix.txt 2>&1
( cd $W/probes; for v in "$@"; do EXPECT_VENV=$v $SB/envs/$v/bin/python -I schema_hashes.py; done ) > $OUT/schema_hashes.txt 2>&1
