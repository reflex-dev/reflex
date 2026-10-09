#!/bin/bash
# Run every Python-level probe and pytest suite of this area with ONE venv (no servers). Usage: bin/run_python_suite.sh [venv=$NEW] [outdir]
# Output: one file per probe in <outdir> (default $W/logs/py/<venv>) plus rc.txt (exit codes) and summary.txt (last line of each).
# Needs pytest/pytest-mock in the venv (build_venvs.sh). Probes that need numpy/pandas are skipped when missing.
. "$(cd "$(dirname "$0")/.." && pwd)/env.sh"
V=${1:-$NEW}; OUT=${2:-$W/logs/py/$V}; PY=$SB/envs/$V/bin/python; mkdir -p "$OUT"; : > "$OUT/rc.txt"
export EXPECT_VENV=$V
R=$W/run/py-$V; rm -rf "$R"; mkdir -p "$R"; cp -r "$CS/probes" "$CS/pytest" "$R/"   # private copy: probes write files / caches
run() { local name=$1 dir=$2; shift 2; ( cd "$dir" && "$@" ) > "$OUT/$name.txt" 2>&1; echo "$name rc=$?" >> "$OUT/rc.txt"; }
P=$R/probes; T=$R/pytest; PT=(-I -m pytest -p no:cacheprovider -p no:randomly -rA -q)
# #7519 (A5-01..A5-05) and the error-message owner
run copydef            "$P"            "$PY" -I probe_copydef.py
run copydef_extra      "$P"            "$PY" -I probe_copydef_extra.py
run v1_late            "$P/v1"         "$PY" -I probe_v1.py
run v1_patchdict       "$P/v1"         "$PY" -I probe_patchdict.py
run lock_tree          "$P"            "$PY" -I probe_lock_tree.py
run lockmod_fevar      "$P/lockmod"    "$PY" -I run_lockmod.py fevar
run lockmod_mystate    "$P/lockmod"    "$PY" -I run_lockmod.py mystate
run owner_msg          "$P"            "$PY" -I probe_owner_msg.py
run docs               "$P"            "$PY" -I probe_docs.py
run default_trap_09    "$P"            "$PY" -I probe_09_default_trap.py
run default_trap2      "$P"            "$PY" -I probe_09_trap2.py
run many_states        "$P"            "$PY" -I probe_many_states.py
if "$PY" -c "import numpy, pandas" 2>/dev/null; then
  for k in list ndarray df dictrows; do run "large_$k" "$P" "$PY" -I probe_large.py $k; done
  for k in rows floats ndarray; do run "mem_${k}_keep" "$P" "$PY" -I probe_mem.py $k keep; done
fi
# field API, storage, threads, internals, schema hash
run internals          "$P"            "$PY" -I probe_internals.py
run shared_default     "$P"            "$PY" -I probe_shared_default.py
run storage_setdefault "$P"            "$PY" -I probe_storage_setdefault.py
run storage_fields     "$P"            "$PY" -I probe_storage_fields.py
run thread_setdefault  "$P"            "$PY" -I probe_thread_setdefault.py
run thread_fields      "$P"            "$PY" -I probe_thread_fields.py
run schema_hashes      "$P"            "$PY" -I schema_hashes.py
run schema_hashes_sd   "$P"            "$PY" -I schema_hashes_sd.py
# A4-01 / A4-02
run addvar             "$P"            "$PY" -I probe_addvar.py
run dynroute           "$P/dynroute"   "$PY" -I probe_dynroute.py
run autoset_on         "$P/autoset_on" "$PY" -I ../probe_autoset2.py
run autoset_off        "$P/autoset_off" "$PY" -I ../probe_autoset2.py
run autoset_orig       "$P/autoset"    "$PY" -I probe_autoset.py
# A3-02 / A3-04 / N-008 / N-006 / F-001 originals
run v8_storage         "$P"            "$PY" -I probe_v8_storage.py
run adv7495            "$P"            "$PY" -I adv7495.py
for m in dev prod; do
  run "guard7495.$m"   "$P"            env REFLEX_ENV_MODE=$m "$PY" -I guard7495.py
  run "guard_local_rename.$m" "$P"     env REFLEX_ENV_MODE=$m "$PY" -I guard_local_rename.py
  run "derive_a.$m"    "$P"            env REFLEX_ENV_MODE=$m "$PY" -I derive_a.py "$V"
done
run derive_e_format    "$P"            "$PY" -I derive_e_format.py "$V"
# pytest suites
run pt_moot            "$T"            "$PY" "${PT[@]}" test_moot.py
run pt_converted       "$T"            "$PY" "${PT[@]}" test_converted.py
run pt_converted_attr  "$T"            "$PY" "${PT[@]}" test_converted_attr.py
run pt_n039_fields     "$T"            "$PY" "${PT[@]}" test_n039_fields.py
run pt_undo_edge       "$T"            "$PY" "${PT[@]}" test_undo_edge.py
run pt_v7_undo         "$T"            "$PY" "${PT[@]}" test_v7_undo.py
run pt_patch_substate  "$T"            "$PY" "${PT[@]}" --tb=short test_patch_substate.py
run pt_min             "$T"            "$PY" "${PT[@]}" test_min.py
run pt_mp_backend_var  "$T"            "$PY" "${PT[@]}" test_monkeypatch_backend_var.py
run pt_mp_other_attrs  "$T"            "$PY" "${PT[@]}" test_monkeypatch_other_attrs.py
if "$PY" -c "import reflex_local_auth, reflex_chat" 2>/dev/null; then
  run pt_n039_downstream "$T"          env DOWNSTREAM=1 "$PY" "${PT[@]}" test_n039_fields.py
  run pt_pkg_states    "$T/downstream" "$PY" "${PT[@]}" test_pkg_states.py
fi
for f in "$OUT"/*.txt; do [ "$(basename "$f")" = rc.txt ] || [ "$(basename "$f")" = summary.txt ] || printf '%-28s %s\n' "$(basename "$f" .txt)" "$(grep -v '^\s*$' "$f" | tail -n 1 | cut -c1-150)"; done > "$OUT/summary.txt"
cat "$OUT/rc.txt"; echo "logs: $OUT"
