ITEM: verify_class_state
KIND: verify
REF: a3_class_state-7
TITLE: #7495 undo stack pops the newest entry: rejected mock.patch.object(Var/Field), an assignment inside a patch window, and monkeypatch.delattr lose a configured class default or leak the patch (CONFIRMED; (a)/(b) only via mock/pytest-mock)
SEVERITY: low
STATUS: confirmed
REGRESSION_VS_0.9.12: no (0.9.12 ignores class-level default assignment; nothing to compare)
REGRESSION_VS_0.10.0a2: yes for (a) (b) (d) (a2 kept the configured default); (c) no (a2 leaked too, loudly, = N-039)
REPRO: Own repro, one state class per case configured at import (C.limit = 10; C._quota = 10):
  mkdir -p $SB/apps/verify_class_state/run && cp -r prerelease_testing/2026-10-07-a3/a3_class_state/verification/probes $SB/apps/verify_class_state/run/
  cd $SB/apps/verify_class_state/run/probes && EXPECT_VENV=verify_class_state-a3 $SB/envs/verify_class_state-a3/bin/python -I -m pytest -p no:cacheprovider -p no:randomly -rA -q -s test_v7_undo.py
  (venv: 'reflex[db]==0.10.0a3' 'reflex-base==0.10.0a3' 'pydantic<2.14' pytest pytest-mock; pytest 9.1.1, pytest-mock 3.16.0)
  a3: 4 failed / 16 passed: (a) mock.patch.object(C,"limit",Other.y) -> 0; (b) mocker.patch.object(C,"_quota",rx.field(5)) -> 0;
  (c) monkeypatch.setattr(C,"limit",99); C.limit = 50 -> 99 after teardown; (d) monkeypatch.delattr(C,"_quota") -> 0 during and after.
  Controls pass (plain monkeypatch/mock round trips, nested patches, rejected wrong-type value).
  Narrowing: monkeypatch.setattr with a Var/Field does NOT lose the default (pytest 9 registers the undo only after a successful
  setattr); unittest.mock's _patch.__enter__ calls __exit__ (assigns the saved Field back = one pop) when setattr raises, and pytest-mock
  uses it. probe_v7_paths.py: only Var and Field values skip _keep_default; every other rejected value round-trips.
  Explorer's test_undo_edge.py re-run: a3 4 failed/4 passed, a2 1 failed/7 passed/1 error, as claimed.
  Docs: base_vars.md says restore "undoes the most recent default assignment" (so (c)/(d) match the literal text) but also promises
  monkeypatch/mock.patch.object round trips, and the __setattr__ docstring says a failed assignment "leaves the default as it was".
  Impact: pytest suites only, silent cross-test leakage; (a)/(b) need an already-failing patch (TypeError the user sees); (c) needs code
  under test that assigns a class default while it is patched (docs discourage runtime assignment); (d) needs monkeypatch.delattr on a
  declared var. Side note confirmed: a plain str assigned to a frontend str var with a declared non-storage default_factory calls that
  factory on a3 (raw RuntimeError surfaces; a2 accepted).
EVIDENCE: prerelease_testing/2026-10-07-a3/a3_class_state/verification/out/f7_own_{a3,a2,s912}.txt, f7_paths_{a3,a2}.txt,
  f7_explorer_{a3,a2}.txt, adv7495_rerun_{a3,a2,s912}.txt; probes/test_v7_undo.py, probes/probe_v7_paths.py; NOTES.md ## VERIFICATION
ROOT_CAUSE_GUESS: reflex_base 0.10.0a3 reflex_base/vars/base.py: BaseStateMeta.__setattr__ 4861-4924 (identity restore 4888-4890;
  _keep_client_storage 4895 and _accepts_default 4896 — which raises for Var 4738-4743 / Field 4744-4749 — run before any _keep_default
  at 4903/4918); Field._restore_default 4130-4133 pops the newest entry regardless of which assignment is undone; __delattr__ 4926-4939 pops.
