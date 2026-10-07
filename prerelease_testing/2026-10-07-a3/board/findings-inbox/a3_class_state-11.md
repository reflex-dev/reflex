ITEM: a3_class_state
KIND: new
REF: N-041
TITLE: AppHarness: a second app in the same pytest process that renders a state from a shared (non-app) module crashes on first render (`useContext` of a missing StateContext) on 0.10; 0.9.12 renders
SEVERITY: low
STATUS: new
REGRESSION_VS_0.9.12: yes
REGRESSION_VS_0.10.0a2: no
REPRO: venv (PyPI): uv --no-config venv --python 3.12 $SB/envs/h; uv --no-config pip install --python $SB/envs/h/bin/python --prerelease=allow
  'reflex[db,testing]==0.10.0a3' 'reflex-base==0.10.0a3' 'pydantic<2.14' pytest 'playwright==1.63.0'.
  Files: a3_class_state/harness/shared/shared_state.py (class SharedCfg(rx.State): count: int = 0; theme: str = rx.LocalStorage(...)),
  a3_class_state/harness/test_shared_state_harness.py (AppHarness apps A, B, C created one after the other in ONE process, each
  `from shared_state import SharedCfg` and renders rx.text(SharedCfg.count)). Run from that dir:
  H_ASSIGN=0 H_VENV=h H_FP=3110 H_BP=8110 PYTHONPATH=$PWD/shared $SB/envs/h/bin/python -m pytest -s -p no:cacheprovider test_shared_state_harness.py
  -> a3: "2 failed, 1 passed" (A passes; B and C never hydrate: browser `TypeError: Cannot read properties of undefined (reading '$$typeof')
  at exports.useContext ... at Bare (app_components/happb/happb.jsx:24)`, logged by the backend as [Reflex Frontend Exception]).
  B's compiled .web/utils/context.jsx has no `...shared_state____shared_cfg` StateContext although happb.jsx uses
  `StateContexts.reflex___state____state__shared_state____shared_cfg`. Same with or without class-level default assignments
  (H_ASSIGN=1/0), and identical on 0.10.0a2. 0.9.12: 3 passed (B renders; its click handler does nothing, the pre-existing N-041).
EVIDENCE: prerelease_testing/2026-10-07-a3/a3_class_state/logs/adv/harness-a3_class_state-a3h-assign{0,1}.log,
  logs/adv/harness-a3_class_state-a2h.log, logs/adv/harness-a3_class_state-s912h.log
ROOT_CAUSE_GUESS: reflex/testing.py AppHarness re-initialisation (#7359) resets the state registration and re-imports only app modules;
  a state class from an already-imported shared module is not re-registered in the new state tree, so compile_contexts omits it while
  the page's Vars still reference it. Unrelated to #7495.
