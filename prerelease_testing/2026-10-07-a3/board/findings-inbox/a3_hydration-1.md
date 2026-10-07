ITEM: a3_hydration
KIND: new
REF: - (side effect of reflex#7493, the N-032 fix)
TITLE: sync=True LocalStorage: the #7493 boot echo writes the value a tab read at CONNECT time, so a change made in another tab while it boots starts an endless cross-tab storage ping-pong (a2 clean, 0.9.12 also storms)
SEVERITY: medium
STATUS: new
REGRESSION_VS_0.9.12: no (0.9.12 storms in 9/10 runs of the same driver; a3 restored 0.9.12's boot echo)
REGRESSION_VS_0.10.0a2: yes (a2 0/15 runs, a3 11/17 runs)
REPRO: SB=<scratch>; W=$SB/apps/a3_hydration (copy of prerelease_testing/2026-10-07-a3/a3_hydration: src drivers scripts srv.sh).
  App src/bootecho: `Prefs.theme: str = rx.LocalStorage("light", name="be_theme", sync=True)` shown in #theme, `rx.input(id="theme-in", on_blur=Prefs.set_theme)`.
  $W/scripts/run_storm.sh a3 dev 8 3142 8142 S 6      # (also: a3 prod 3144 3144, alpha2, stable)
  = drivers/sync_race.py Part S: one browser context; tab0 loads `/` and sets theme "s0"; then 6 more tabs goto `/` concurrently while
  tab0 sets theme s1..s5 250 ms apart (fill #theme-in + blur). After hydration + 4 s: read #theme in every tab, count `storage`
  events and websocket frames in the next 2 s. Correct = every tab shows s5, 0 frames in the quiet window.
  Long form (60 s observation, backend CPU): `drivers/sync_race.py http://localhost:3142 out.json 2500 6 S 60`.
  Part R (deterministic 2-tab form, transient revert): `$W/scripts/run_storm.sh a3 dev 2 3142 8142 R` — tab B boots with its inbound
  websocket messages held 2.5 s (Playwright route_web_socket) while tab A changes v1->v2: on a3 A shows v1 again (storage events
  v2->v1->v2), a2 never does.
EVIDENCE: a3_hydration/NOTES.md §3; results/sync/storm_*.json, race_*.json, storm_long_a3_dev_{1,2,3}.json; trimmed/st-a3-dev-1.trimmed.log, st-long-1.trimmed.log.
  Part S: a3 dev 6/9 (+3/3 long runs; 5 tabs 3/6; 2-3 tabs 0/12), a3 prod 2/5; a2 dev 0/10, a2 prod 0/5; 0.9.12 dev 9/10.
  A storm never decays: 60 s observation, 17k-39k frames per 5 s window, 2-9k storage events per tab, tabs stuck on mixed stale
  values (s2/s3/s4; the user's last value s5 is lost), backend python ~50-70% CPU for the whole time. No console error, no server error.
  Part R: a3 1/2 (A timeline v1 -> v2 -> v1 -> v2), a2 0/2, 0.9.12 2/2.
ROOT_CAUSE_GUESS: reflex/state.py:2401 + 2420-2422 (published a3): hydrate_and_load re-marks every browser-provided storage var dirty after
  the snapshot, so the final boot delta carries the value read from localStorage when the CONNECT was built; the frontend writes it
  (reflex_base/.templates/web/utils/state.js:896 applyClientStorageDelta -> :1076 localStorage.setItem) even if another tab changed the
  key meanwhile. That stale write fires `storage` in every other tab (state.js:1267 handleStorage -> update_vars_internal), whose deltas
  write back again; with >=2 values in flight and >=4 tabs the loop sustains itself (the generic loop is a3_hydration-2). a2 never wrote
  at boot. A fix could skip the echo for sync=True keys whose localStorage value changed since the CONNECT (frontend: compare before
  setItem against the value sent at boot), or not echo unchanged browser values back to storage at all (the echo is only needed for
  get_delta overrides that CHANGE the value).
