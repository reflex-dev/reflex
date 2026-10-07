ITEM: verify_hydration
KIND: verify
REF: A3-11
TITLE: CONFIRMED (conditions broader than written): with sync=True LocalStorage, ONE change made in a tab while another tab of the same browser is booting makes the #7493 boot echo write the stale value back; 3 tabs then ping-pong forever (2 tabs: visible flicker). Regression vs a2, not vs 0.9.12 (same mechanism, wider window there)
SEVERITY: medium
STATUS: confirmed
REGRESSION_VS_0.9.12: no (0.9.12 storms in the same settings: raw background tabs 3/3, 7-tab restore 6/6, explorer Part S 2/2)
REGRESSION_VS_0.10.0a2: yes (a2 0/10 runs in which a tab demonstrably booted across the click; a3 storms in every such run with 3+ tabs in dev, 2/2 in prod+Redis raw)
REPRO: SB=<scratch>; V=$SB/apps/verify_hydration; mkdir -p $V/{run,logs,out}; cp -r prerelease_testing/2026-10-07-a3/a3_hydration/verification/{src,drivers,scripts} $V/
  $V/scripts/vlproxy.sh start 8661 8660 50          # 100 ms RTT, as for any non-local server
  $V/scripts/vsrv.sh start vh-a3-dev a3 dev $V/src/vhsync 3660 8660 REFLEX_API_URL=http://localhost:8661
  $V/scripts/vraw.sh a3dev_rtt100_raw3 3 3660 3 300 pick-red 200 10     # stock headful Chromium under xvfb, tabs 1-2 are REAL background tabs
  = returning user (profile holds vh_theme=green); browser restart restores 3 tabs (tab i starts at i x 300 ms); the user clicks "red"
    once, 200 ms after the foreground tab hydrates. Correct: every tab shows red, no traffic. a3: endless red<->green ping-pong.
  Compare: same commands with venv alpha2 (quiet) and stable (storms). Prod: vsrv.sh start ... a3 prod ... 3662 3662 REFLEX_API_URL=http://localhost:3663
  REFLEX_REDIS_URL=redis://localhost:8669 behind vlproxy.sh start 3663 3662 50.  Trigger check: scripts/vtrigger.py out/*.json
EVIDENCE: a3_hydration/NOTES.md "## VERIFICATION"; verification/results/summary.json + all_runs_summary.txt; verification/traces/a3dev_rtt100_raw3_1.trace.txt
  (tab1 CONNECT reads green, red lands, tab1's final boot delta `is_hydrated:true, prefs.theme:"green"` rewrites green), a2dev_rtt100_raw3_1 (same timing, boot delta
  has no theme, quiet), s912dev_..._1click_1 (0.9.12: update_vars_internal boot delta echoes green), trigger_check.txt, user_tab_revert.txt, results/cpu_sample_a3dev_raw3.txt.
  Numbers: a3 raw 3 tabs 3/3 + 60 s run (22-27k frames/5 s, no decay) + 30 s run; 2 tabs: user's tab flips back to the old value 3-53x, 1/5 kept looping >10 s;
  prod+Redis 2/2 triggered; 7-tab Playwright restore: every triggered run stormed; a later user click is swallowed; backend ~72 % CPU avg / 117 % sampled for 3 tabs;
  localStorage ends on the OLD value in 3/10 a3 storms. Not a Playwright artefact (stock Chromium, hidden + throttled tabs, no held messages; the storm path uses no timers).
  Explorer's localhost Part S rate NOT reproduced (a3 0/7 here vs 6/9; a2 0/3; 0.9.12 2/2): on localhost a3's CONNECT->echo window is ~10 ms, so that rate is load-dependent;
  Part R (held inbound 2.5 s) reproduced 3/3 (a2 0/3). Prototype on a scratch compiled state.js: skipping an unchanged boot echo alone removes it (0/3, a2-like).
ROOT_CAUSE_GUESS: reflex/state.py:2401 + 2420-2422 (hydrate_and_load re-marks the browser-provided values dirty, so the final boot delta carries the value read at CONNECT)
  -> reflex_base/.templates/web/utils/state.js:896 applyClientStorageDelta -> :1076 localStorage.setItem (stale value over a newer one) -> :1267-1277 handleStorage
  (e.newValue) -> update_vars_internal (state.py:2738) answers are written back again. Fix belongs in the boot echo: do not write back an UNCHANGED echo (frontend:
  skip a sync key whose boot-delta value equals what the tab sent in its hydrate payload; or backend: after get_delta drop storage entries equal to the browser value),
  keeping #7493's re-mark so get_delta overrides still see the values.
