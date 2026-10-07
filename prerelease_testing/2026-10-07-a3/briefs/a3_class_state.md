# Item `a3_class_state` — N-005, N-039, N-008, N-006, N-004 on 0.10.0a3 and regressions from reflex#7495 / #7494

Ports: frontend 3100-3119, backend 8100-8119 (redis 8109). Work dir: $SB/apps/a3_class_state/.
DEST: /home/user/reflex/prerelease_testing/2026-10-07-a3/a3_class_state/
Venvs: $SB/envs/a3 (under test), $SB/envs/alpha2, $SB/envs/stable. Make your own venvs for pytest/pytest-mock and Python 3.11/3.13/3.14 runs.

Read first: ../CAMPAIGN_STATE.md, ../AGENT_BRIEF.md, ../../2026-10-07/FINDINGS.md N-004, N-005, N-006, N-008, N-039, N-040 (incl. VERIFICATION
paragraphs), ../../2026-10-07/reverify_core/NOTES.md, ../../2026-10-07/thirdparty_a2/verification/NOTES.md. Read the a3 diffs:
`git -C /home/user/reflex diff v0.10.0a2 555b667c1 -- packages/reflex-base/src/reflex_base/vars/base.py reflex/state.py` (PRs #7494, #7495).

## Do
1. Original repros, unchanged, on a3 (and the a2 numbers next to them):
   - N-005: reverify_core/verification/n005-storage-assign (storage_assign_matrix.py: 3 storage types × str/storage annotation × 6 assignment
     kinds), derive_g_assign.py, derive_i_storage_legacy.py, reverify_hydration/probes/cs_storage_default_probe.py + src/csbox, the core_a2
     `/storage` e2e (drive_core.py) in dev and prod+redis: the browser must persist `ls_plain_key`, `lscs_key`, cookie `ck_key`.
   - N-039: thirdparty_a2/pytest_probe/min/test_min.py and the verifier's full matrix (thirdparty_a2/verification/run_all.sh: 15 var kinds × 7
     patch mechanisms incl. pytest-mock, substate patching, delattr) on Python 3.11–3.14.
   - N-008: derive_f_dunder.py (dev): `self._sneaky__name = 1` must raise; mixin/base/underscore-class `self.__counter` must still be allowed.
   - N-006: derive_e_format.py: the message must name `default_value()` / `ClassVar` / a state var.
   - N-040: re-run its probes; expected unchanged (documented) — report only differences.
   - N-004 (now documented, not fixed): derive_h_schema.py matrix + n004-schema-rollback fleet e2e with one Redis and one disk store:
     0.9.12 → a3 keeps the session; a3 → 0.9.12 resets cleanly (no traceback, fresh state) — matches the new breaking-change note;
     a2 → a3 and a3 → a3 keep sessions (if a2 → a3 resets, report it: alphas share the 0.10 format); check the schema hash of one app
     on a2 vs a3, and that a3's pickle has no `_PREVIOUS_RELEASE_PICKLE_KEYS` entries and no `_replaced_defaults`.
2. Regression hunt for #7495 (adversarial): assignment on a parent/mixin/substate, ComponentState.create per-instance defaults and
   `cls.x = ...` in get_component across several instances, reset() after assignment and after restore, >16 assignments then restores,
   `del State.x` with nothing assigned, a rejected assignment (TypeError) followed by a restore, storage factories (declared and
   assigned) called exactly once, `str`-annotated storage var vs storage-annotated var (#7498/#7499 are known, don't re-report), pickling
   a state whose class has an undo stack (Redis + disk), prod with several granian workers, AppHarness-style reuse of a state class
   across apps, thread safety of class assignment if you can make it matter. Each anomaly: compare with alpha2 and 0.9.12.
Write one inbox file per finding (one reverify file per N-id). Copy artifacts to DEST as you go; commit per the protocol.
