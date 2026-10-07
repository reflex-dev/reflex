ITEM: a3_hydration
KIND: new
REF: -
TITLE: sync=True LocalStorage written by several tabs at once (e.g. an on_load that stamps a synced var, browser session restore) loops forever between the tabs (pre-existing, all versions)
SEVERITY: medium
STATUS: new
REGRESSION_VS_0.9.12: no (0.9.12 3/3 storms)
REGRESSION_VS_0.10.0a2: no (a2 storms with 3 tabs 2/3, 6 tabs 2/2 completed runs)
REPRO: SB=<scratch>; W=$SB/apps/a3_hydration. App src/syncstamp: `Stamp.last: str = rx.LocalStorage("", name="ss_last", sync=True)`;
  page /stamp has `on_load=Stamp.on_load_stamp` which sets `last = f"{client_token[:6]}-{loads}"` (a different value per tab).
  $W/scripts/run_stamp.sh a3 dev 4 3142 8142 /stamp 6     # also alpha2 / stable; /stamp 2 and 3 tabs; control: /same (every tab writes "same")
  = drivers/stamp_storm.py: one context, warm-up tab, then 6 tabs goto /stamp concurrently; frames counted in-page (WebSocket wrapper),
  2 windows of 5 s after hydration + 3 s.
EVIDENCE: a3_hydration/results/stamp/stamp_*.json, NOTES.md §3b. a3 6 tabs: 2/2 completed runs storm (41k-234k frames / 5 s; tabs end on
  2-3 different values); a2 6 tabs 2/2 completed runs storm (one converged on a single value but kept looping at 118k frames/5 s),
  3 tabs 2/3, 2 tabs 0/3; 0.9.12 6 tabs 3/3. Control /same (identical value from every tab): quiet on a3 3/3. The volume also crashed
  the Playwright node driver (`write EINVAL`) in 4 of 12 runs until frames were counted in-page.
ROOT_CAUSE_GUESS: feedback loop without versioning: storage event -> update_vars_internal (state.js:1267-1276) -> delta carries the var
  -> applyClientStorageDelta setItem (state.js:1076) fires `storage` in every other tab whenever the value differs from what another tab
  wrote meanwhile; two values in flight never die out. Unchanged in a2/a3 (state.js byte-identical). Possible fix: do not write a
  sync=True key back from a delta that was caused by that key's own storage event (or only setItem when the backend value differs from
  the value the event carried).
