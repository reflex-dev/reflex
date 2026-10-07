#!/usr/bin/env bash
# Re-run every T-1 / T-2 verification probe against PyPI-installed reflex 0.10.0a2, 0.10.0a1 and 0.9.12.
#
#   SB=<scratchpad root> bash run_all.sh [OUTDIR]
#
# Rules followed: everything is installed from PyPI into isolated venvs under $SB/envs (never from a checkout);
# every probe runs with `python -I` from a neutral directory and asserts which venv's reflex it imported.
# No server, redis or browser is started (Python-level verification), so no ports are used.
set -u
SB=${SB:?set SB to the scratchpad root (the directory that contains envs/ and apps/)}
HERE=$(cd "$(dirname "$0")" && pwd)
case "$HERE" in
  /home/user/reflex|/home/user/reflex/*|/home/user/reflex-enterprise|/home/user/reflex-enterprise/*)
    echo "refusing to run from inside a checkout ($HERE): copy this directory to a neutral place first," \
         "e.g.  cp -r \"$HERE\" \"\$SB/apps/verify_tp_0_rerun\"  and run it there" >&2
    exit 2 ;;
esac
OUT=${1:-$HERE/out_rerun}
mkdir -p "$OUT"
export REFLEX_TELEMETRY_ENABLED=false

make_venv() {  # name, pin file, python version
  local name=$1 pins=$2 py=${3:-3.12}
  if [ ! -x "$SB/envs/$name/bin/python" ]; then
    (cd "$SB" && uv --no-config venv --python "$py" "$SB/envs/$name" &&
      uv --no-config pip install --python "$SB/envs/$name/bin/python" --prerelease=allow -r "$pins") || return 1
  fi
}
# exact pins (a freeze of the campaign venvs, pydantic held at 2.13.5 for all three, + pytest, pytest-mock; greenlet is
# part of the freeze because a fresh reflex[db] on sqlalchemy 2.1 needs it, see campaign finding N-001)
make_venv verify_tp_0-a2 "$HERE/reqs/a2.all.txt"
make_venv verify_tp_0-a1 "$HERE/reqs/a1.all.txt"
make_venv verify_tp_0-s0912 "$HERE/reqs/s0912.all.txt"

PROBES=$HERE/probes
cd "$PROBES" || exit 1
run() {  # label, venv name, command...
  local label=$1 venv=$2; shift 2
  echo "== $label  ($venv)"
  EXPECT_VENV=$venv "$SB/envs/$venv/bin/python" -I "$@" >"$OUT/$label.txt" 2>&1
  echo "   exit=$? -> $OUT/$label.txt"
}

for n in a2 a1 s0912; do
  v=verify_tp_0-$n
  run t1_matrix.$n "$v" t1_matrix.py "$OUT/t1_matrix.$n.json"
  run t1_pytest.$n "$v" -m pytest -p no:cacheprovider -p no:randomly -rA -q --no-header --tb=line test_t1_pytest.py
  run t1_method_patterns.$n "$v" -m pytest -p no:cacheprovider -p no:randomly -q --no-header --tb=line test_t1_method_patterns.py
  run t1_documented.$n "$v" t1_documented.py
  run t2_matrix.$n "$v" t2_matrix.py "$OUT/t2_matrix.$n.json"
  run t2_mock_called.$n "$v" t2_mock_called.py
  run t2_deferred_deepcopy.$n "$v" t2_deferred_deepcopy.py
  run t2_classvar_migration.$n "$v" t2_classvar_migration.py
done
run t1_blast_radius.a2 verify_tp_0-a2 t1_blast_radius.py
run cause_experiment.a2 verify_tp_0-a2 cause_experiment.py

# side-by-side tables (any venv's python works; they only read the JSON)
"$SB/envs/verify_tp_0-a2/bin/python" -I t1_compare.py "$OUT" >"$OUT/t1_compare.txt"
"$SB/envs/verify_tp_0-a2/bin/python" -I t2_compare.py "$OUT" >"$OUT/t2_compare_all.txt"
echo "== side-by-side tables: $OUT/t1_compare.txt $OUT/t2_compare_all.txt"

# optional: the campaign's third-party venvs (22 packages from PyPI; created by the thirdparty_a2 explorer)
declare -A TP=([a2]=thirdparty_a2-a2 [a1]=thirdparty-alpha [s0912]=thirdparty-stable)
for n in a2 a1 s0912; do
  v=${TP[$n]}
  if [ -x "$SB/envs/$v/bin/python" ]; then
    run clerk_probe.$n "$v" clerk_probe.py
    run dynoselect_slot_probe.$n "$v" dynoselect_slot_probe.py
  else
    echo "   (skip third-party probes for $n: venv $v not present)"
  fi
done
if [ -x "$SB/envs/thirdparty_a2-a2/bin/python" ]; then
  SITE=$SB/envs/thirdparty_a2-a2/lib/python3.12/site-packages
  "$SB/envs/thirdparty_a2-a2/bin/python" -I scan_thirdparty.py "$SITE" \
    reflex-ag-grid reflex-audio-capture reflex-calendar reflex-chakra reflex-chat reflex-clerk reflex-color-picker \
    reflex-dynoselect reflex-global-hotkey reflex-google-auth reflex-google-recaptcha-v2 reflex-image-zoom \
    reflex-intersection-observer reflex-local-auth reflex-magic-link-auth reflex-monaco reflex-motion reflex-pyplot \
    reflex-qrcode reflex-simpleicons reflex-type-animation reflex-webcam >"$OUT/scan_thirdparty.txt" 2>&1
  echo "== AST scan of the 22 packages: $OUT/scan_thirdparty.txt (plus the regex cross-check commands in NOTES.md)"
fi
echo "done."
