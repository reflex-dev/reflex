ITEM: a3_class_state
KIND: new
REF: N-039
TITLE: #7495 undo-stack restore is "pop the latest" not "put back what was saved": four patch patterns silently lose a configured class default or leak the patched one
SEVERITY: low
STATUS: new
REGRESSION_VS_0.9.12: no
REGRESSION_VS_0.10.0a2: yes
REPRO: venv: uv --no-config venv --python 3.12 $SB/envs/x; uv --no-config pip install --python $SB/envs/x/bin/python --prerelease=allow
  'reflex[db]==0.10.0a3' 'reflex-base==0.10.0a3' 'pydantic<2.14' pytest pytest-mock. Test file (a3_class_state/probes/undo_edge/test_undo_edge.py):
  class Svc(rx.State): limit: int = 0; _quota: int = 0  ... then module-level `Svc.limit = 10; Svc._quota = 10` (documented config).
  (a) `with pytest.raises(TypeError): with mock.patch.object(Svc, "limit", Other.y): pass` -> next test sees limit 0, not 10
  (b) `mocker.patch.object(Svc, "_quota", rx.field(5))` (TypeError) -> next test sees _quota 0
  (c) `monkeypatch.setattr(Svc, "limit", 99); Svc.limit = 50` (code under test reconfigures) -> after teardown limit is 99 (the PATCH leaks)
  (d) `monkeypatch.delattr(Svc, "_quota")` -> during the test _quota reads 0, after teardown still 0 (config lost for good)
  Run: EXPECT_VENV=x $SB/envs/x/bin/python -I -m pytest -p no:cacheprovider -p no:randomly -rA -q test_undo_edge.py
  a3: 4 failed, 4 passed (all four sentinels fail: 0, 0, 99, 0 instead of 10). a2: 1 failed, 7 passed, 1 error (only (c), and loudly).
  0.9.12 ignores class assignments, so the comparison does not apply there.
  Related (probes/adv7495.py, logs/adv/adv7495.a3.txt): `S.count = 10; S.count = S.count` silently reverts to 0 (self-assignment = undo);
  >16 nested patches cannot reach the original default (documented limit); a str var declared with a non-storage
  `default_factory` now has that factory CALLED when a plain str is assigned (side effects at import; a raising factory surfaces its raw
  exception, e.g. RuntimeError, instead of TypeError, a2 accepted the assignment).
EVIDENCE: prerelease_testing/2026-10-07-a3/a3_class_state/logs/adv/test_undo_edge.txt, logs/adv/adv7495.{a3,a2,s0912}.txt
  (cases rejected_var_then_undo_mock, monkeypatch_delattr_with_config, patch_then_runtime_assign_then_undo, self_assign_after_config,
  over16_*, declared_factory_raises_on_plain_assign)
ROOT_CAUSE_GUESS: reflex_base/vars/base.py (published 0.10.0a3): __setattr__ 4895-4896 call _keep_client_storage (may call the declared
  factory, 4778) and _accepts_default (raises TypeError for Var 4743 / Field 4749) BEFORE any _keep_default (4903/4918), so those failed
  assignments push no undo entry while mock's __exit__ (and pytest-mock) still restore -> _restore_default pops the user's earlier entry;
  __delattr__ (4926-4939) pops instead of deleting, and the saved Field is then assigned back -> second pop; restoring by identity
  (4888) pops whatever was pushed last, so any assignment made inside the patch window is undone instead of the patch.
  Fix idea: push the keep entry before any validation (try/except around the whole body), and/or record a token per assignment
  (restore the entry matching the saved object rather than the last one).
