ITEM: a3_class_state
KIND: reverify
REF: N-039
TITLE: Class-level patch/restore of a State var default (monkeypatch, mock.patch.object, pytest-mock, substate, delattr) round-trips on 0.10.0a3, Python 3.11-3.14
SEVERITY: medium
STATUS: fixed
REGRESSION_VS_0.9.12: no
REGRESSION_VS_0.10.0a2: no
REPRO: SB=...scratchpad; venvs (PyPI): uv --no-config venv --python 3.1x $SB/envs/a3_class_state-a3[-py311|-py313|-py314];
  uv --no-config pip install --python <venv>/bin/python --prerelease=allow 'reflex[db]==0.10.0a3' 'reflex-base==0.10.0a3' 'pydantic<2.14' pytest pytest-mock
  (a3_class_state/bin/build_a3_venvs.sh). Then a3_class_state/bin/tpv_run.sh <out> a3=a3_class_state-a3 a3py311=... (runs the ORIGINAL
  thirdparty_a2/pytest_probe/min/test_min.py and thirdparty_a2/verification/probes unchanged).
  test_min.py: a3 "2 passed" on 3.11/3.12/3.13/3.14 (a2 "1 failed, 1 passed, 1 error"). t1 matrix (15 var kinds x 7 mechanisms):
  monkeypatch and mock.patch.object 0 undo errors / 0 leaks / 15 visible (a2 15/15/15); getattr-restore 0/0/15; delattr 0/0/0;
  test_t1_pytest.py 22 passed (a2 8 failed, 6 errors); blast radius: nothing leaks to parent/sibling/mixin/ComponentState.
  Unchanged residue: manual "re-assign the original value" still fails for `_v: int = None` (annotation rejects its own default), and
  test_monkeypatch_backend_var.py::test_monkeypatch_setattr_mock fails because an unspecced Mock is called and rejected (N-040, documented).
EVIDENCE: prerelease_testing/2026-10-07-a3/a3_class_state/logs/tpv/compare_all.txt, logs/tpv/test_min.*.txt, logs/tpv/t1_*.a3*.txt
ROOT_CAUSE_GUESS: fixed by reflex_base/vars/base.py:4110-4140 (_assign_default/_restore_default/_keep_default undo stack), 4888 (field/Var
  identity restore), 4926 (__delattr__). Edge cases of the undo-stack design that still lose or leak defaults: a3_class_state-7.
