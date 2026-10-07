ITEM: a3_class_state
KIND: reverify
REF: N-040
TITLE: Class assignment to unannotated/too-narrow slots still raises and still calls assigned callables (unchanged, now documented)
SEVERITY: low
STATUS: still-broken
REGRESSION_VS_0.9.12: yes
REGRESSION_VS_0.10.0a2: no
REPRO: a3_class_state/bin/tpv_run.sh (ORIGINAL t2_matrix.py, min_t2.py, t2_mock_called.py, t2_deferred_deepcopy.py, t2_classvar_migration.py):
  a3 = a2 exactly: 179/255 assignments raise, user code ran in 42, `_client = None` <- object() "expected <class 'NoneType'>",
  deferred "cannot pickle '_thread.RLock'" on a permissive slot; Python 3.11/3.13/3.14 identical. Only difference: spec_mock_restore
  now restores cleanly (N-039 fix). docs/vars/base_vars.md (#7496) now carries the "Annotate the var, and keep shared objects out of
  defaults" warning, matching the verifier's ClassVar advice.
EVIDENCE: prerelease_testing/2026-10-07-a3/a3_class_state/logs/tpv/t2_*.a3*.txt, logs/tpv/compare_all.txt (t2 totals)
ROOT_CAUSE_GUESS: documented #7461 design (reflex_base/vars/base.py _accepts_default 4725, callable validation in __setattr__ ~4897)
