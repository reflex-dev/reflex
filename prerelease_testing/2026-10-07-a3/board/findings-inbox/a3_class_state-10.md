ITEM: a3_class_state
KIND: new
REF: N-039
TITLE: Concurrent class-default assign/restore from several threads leaves a stale patched default (undo stack and default/default_factory pair are not updated atomically)
SEVERITY: low
STATUS: new
REGRESSION_VS_0.9.12: no
REGRESSION_VS_0.10.0a2: no
REPRO: a3_class_state/probes/adv7495.py thread_stress (needs pytest venv): 8 threads x 1500 iterations of
  `S.count = i; S.count = S.__dict__["count"]` and `S._f = lambda: ...; S._f = S.__dict__["_f"]` with sys.setswitchinterval(1e-6):
  a3 (3 runs, py3.12): count ends 31376 / 0 / 70773 instead of 0, `_f` ends with a thread's patched factory (default MISSING) instead of
  'd'; py3.14 similar. No exception. a2 raised 12000 TypeErrors and also ended corrupted; 0.9.12 ignores assignments.
  Matters only for threaded patching (e.g. pytest-run-parallel / free-threaded test runs) or runtime assignment from threads, which
  the docs already discourage ("Assign defaults before the app starts running").
EVIDENCE: prerelease_testing/2026-10-07-a3/a3_class_state/logs/adv/adv7495.{a3,a3-py311,a3-py314}.txt (thread_stress_assign_restore)
ROOT_CAUSE_GUESS: reflex_base/vars/base.py Field._assign_default 4110-4128 (append then two attribute writes) / _restore_default 4130; no lock
