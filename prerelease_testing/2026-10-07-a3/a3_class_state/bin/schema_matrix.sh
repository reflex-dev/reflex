#!/bin/bash
# Usage: schema_matrix.sh <outfile> <venv> [<venv> ...]
# N-004 Python level: the ORIGINAL derive_h_schema.py (orig/rc_scripts/schema) saves SchemaState with each venv (default 0)
# and loads every save with every venv at default 0 and 5; then dumps each save's keys with probes/pickle_keys.py.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a3_class_state
OUT=$1; shift; D=$W/out/schema; mkdir -p $D; export REFLEX_TELEMETRY_ENABLED=false
cd $W/orig/rc_scripts/schema || exit 1
{
for s in "$@"; do
  echo "+ SCHEMA_DEFAULT=0 $s save"; SCHEMA_DEFAULT=0 $SB/envs/$s/bin/python derive_h_schema.py $s save $D/saved-$s.bin
  for l in "$@"; do for d in 0 5; do
    printf "saved=%-8s d0 -> " "$s"; SCHEMA_DEFAULT=$d $SB/envs/$l/bin/python derive_h_schema.py $l load $D/saved-$s.bin
  done; done
done
echo "+ pickle contents"
for s in "$@"; do $SB/envs/driver/bin/python -I $W/probes/pickle_keys.py $D/saved-$s.bin; done
} > $OUT 2>&1
cat $OUT
