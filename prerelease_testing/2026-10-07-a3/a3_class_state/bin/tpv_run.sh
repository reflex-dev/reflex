#!/bin/bash
# Usage: tpv_run.sh <outdir> <label>=<venv> [<label>=<venv> ...]
# Runs the ORIGINAL thirdparty_a2 verification probes (N-039 t1_*, N-040 t2_*) unchanged (copies under orig/tpv/probes)
# plus the explorer's minimal repro orig/tp_min/min/test_min.py, with each venv. EXPECT_VENV guards name the venv.
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a3_class_state
OUT=$1; shift; mkdir -p $OUT
export REFLEX_TELEMETRY_ENABLED=false
run() { local label=$1 venv=$2; shift 2
  EXPECT_VENV=$venv "$SB/envs/$venv/bin/python" -I "$@" >"$OUT/$label.txt" 2>&1; echo "$label exit=$?" | tee -a $OUT/rc.txt; }
for pair in "$@"; do n=${pair%%=*}; v=${pair#*=}
  cd $W/orig/tp_min/min && run test_min.$n $v -m pytest -p no:cacheprovider -p no:randomly -rA -q --no-header test_min.py
  cd $W/orig/tpv/probes
  run test_min_t1.$n $v -m pytest -p no:cacheprovider -p no:randomly -rA -q --no-header test_min_t1.py
  run t1_matrix.$n $v t1_matrix.py "$OUT/t1_matrix.$n.json"
  run t1_pytest.$n $v -m pytest -p no:cacheprovider -p no:randomly -rA -q --no-header --tb=line test_t1_pytest.py
  run t1_method_patterns.$n $v -m pytest -p no:cacheprovider -p no:randomly -q --no-header --tb=line test_t1_method_patterns.py
  run t1_documented.$n $v t1_documented.py
  run t1_blast_radius.$n $v t1_blast_radius.py
  run cause_experiment.$n $v cause_experiment.py
  run spec_mock_restore.$n $v spec_mock_restore.py
  run min_t2.$n $v min_t2.py
  run t2_matrix.$n $v t2_matrix.py "$OUT/t2_matrix.$n.json"
  run t2_mock_called.$n $v t2_mock_called.py
  run t2_deferred_deepcopy.$n $v t2_deferred_deepcopy.py
  run t2_classvar_migration.$n $v t2_classvar_migration.py
  cd $W/orig/tp_min && run tp_backend_var.$n $v -m pytest -p no:cacheprovider -p no:randomly -rA -q --no-header --tb=line test_monkeypatch_backend_var.py
  run tp_other_attrs.$n $v -m pytest -p no:cacheprovider -p no:randomly -rA -q --no-header --tb=line test_monkeypatch_other_attrs.py
done
