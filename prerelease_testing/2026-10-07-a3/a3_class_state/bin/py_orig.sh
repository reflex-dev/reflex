#!/bin/bash
# Usage: py_orig.sh <venv-name> [outdir]  -- run the ORIGINAL a2-pass Python repros (unchanged copies under orig/) with one venv.
# N-005: storage_assign_matrix.py, derive_g_assign.py (dev+prod), derive_i_storage_legacy.py, cs_storage_default_probe.py
# N-008: derive_f_dunder.py (dev+prod); N-006: derive_e_format.py; context: derive_a/b/b_reset/workarounds
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a3_class_state
V=$1; OUT=${2:-$W/logs/py/$V}; mkdir -p $OUT
export REFLEX_TELEMETRY_ENABLED=false
PY=$SB/envs/$V/bin/python
cd $W/orig/rc_scripts || exit 1
for m in dev prod; do
  for s in derive_f_dunder derive_g_assign derive_a derive_b derive_b_reset derive_workarounds; do
    REFLEX_ENV_MODE=$m $PY $s.py $V > $OUT/$s.$m.txt 2>&1; echo "$s.$m rc=$?" >> $OUT/rc.txt
  done
done
for s in derive_e_format derive_i_storage_legacy; do $PY $s.py $V > $OUT/$s.txt 2>&1; echo "$s rc=$?" >> $OUT/rc.txt; done
cd $W/orig/n005/scripts && $PY storage_assign_matrix.py $V > $OUT/storage_assign_matrix.txt 2>&1; echo "storage_assign_matrix rc=$?" >> $OUT/rc.txt
cd $W/orig/hyd && $PY cs_storage_default_probe.py $V > $OUT/cs_storage_default_probe.txt 2>&1; echo "cs_storage_default_probe rc=$?" >> $OUT/rc.txt
echo "done $V -> $OUT"; cat $OUT/rc.txt
