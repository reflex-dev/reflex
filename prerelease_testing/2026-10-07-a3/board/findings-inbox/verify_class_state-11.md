ITEM: verify_class_state
KIND: verify
REF: a3_class_state-11
TITLE: AppHarness second app rendering a state from a shared module crashes on first render — REFUTED as a 0.10 regression: 0.9.12 crashes identically; same root cause as reflex#7479
SEVERITY: low
STATUS: refuted
REGRESSION_VS_0.9.12: no (0.9.12 shows the same `$$typeof` crash when the page renders the shared state)
REGRESSION_VS_0.10.0a2: no
REPRO: cd $SB/apps/verify_class_state/run/probes && EXPECT_VENV=verify_class_state-<v> V_PREIMPORT=<0|1> V_PORT_BASE=3600 V_OUT=<dir>
  REFLEX_TELEMETRY_ENABLED=false $SB/envs/verify_class_state-<v>/bin/python -I -m pytest -s -p no:cacheprovider -p no:randomly test_v11_two_apps.py
  (venv adds 'reflex[db,testing]' + playwright==1.63.0). Two apps, one after the other, both render `from vshared_state import SharedCounter`.
  V_PREIMPORT=0: app two shows the error boundary "TypeError: Cannot read properties of undefined (reading '$$typeof') at exports.useContext"
  and its context.jsx lacks the shared state on a3, a2 AND 0.9.12. V_PREIMPORT=1 (test module imports the shared module before the first
  harness): both apps render and both handlers work on a3 and 0.9.12.
  Explorer's own harness/test_shared_state_harness.py on 0.9.12 with H_ASSIGN=0: "2 failed, 1 passed", same crash. The claimed 0.9.12
  "3 passed" used H_ASSIGN=1: on 0.9.12 `SharedCfg.count = 10` replaces the class attribute with a plain value, so the pages rendered static
  text ("10"/"dark-a"; even app A's bump did nothing) and never referenced the shared StateContext.
  Recommendation: add this symptom (render crash when the page renders the shared state) and the workaround (import the shared module
  before the first AppHarness) to reflex#7479 instead of filing it as new.
EVIDENCE: prerelease_testing/2026-10-07-a3/a3_class_state/verification/logs/v11-{a3-pre0,a3-pre1,a2-pre0,s912-pre0,s912-pre1}.log,
  logs/explorer-harness-s912-assign0.log, out/v11-*.json, screenshots/v11-*.png; NOTES.md ## VERIFICATION
ROOT_CAUSE_GUESS: identical in 0.9.12 and 0.10.0a3: reflex/testing.py 296-304 forks AppHarness._base_registration_context per app; a state
  registers into the context active at its first import (reflex/state.py:807 -> reflex_base/registry.py 192-221 in reflex-base 0.10.0a3;
  0.9.12 state.py:1101, registry 184-213); _reload_state_module (testing.py 322-331) reloads only the app package, so a shared module first
  imported inside app one never reaches app two's registration context.
