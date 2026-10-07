ITEM: a3_hydration
KIND: reverify
REF: F-002
TITLE: First load no longer persists client-storage defaults — still fixed on 0.10.0a3 (dev, prod, prod+redis), including after #7493's boot echo
SEVERITY: high
STATUS: fixed
REGRESSION_VS_0.9.12: no
REGRESSION_VS_0.10.0a2: no
REPRO: SB=<scratch>; W=$SB/apps/a3_hydration (copy of prerelease_testing/2026-10-07-a3/a3_hydration).
  Positive control: $W/scripts/srv.sh start f1combo-a1 alpha prod $W/src/f1combo 3140 3140; $NP $DRV $W/drivers/f1_check.py http://localhost:3140/ - - out.json pl-ls,wu-ls,wu-sync,cs-ls,cu-ls,ws-ls,wt-ls  -> 0.10.0a1 writes 8 defaults.
  $W/scripts/run_f002.sh a3 prod a3_prod 3140 3140 ; $W/scripts/run_f002.sh a3 dev a3_dev 3142 8142 ; (baseline: alpha2)
  #7493 form: $W/scripts/run_be.sh a3 <dev|prod> <label> <FP> <BP> [REFLEX_REDIS_URL=redis://localhost:8149]  (src/bootecho, drivers/bootecho_check.py: fresh_index/onload/plainload)
  mini: srv.sh start mini-a3 a3 prod src/mini_writeback 3141 3141 (+ MINI_THEME_DEFAULT=dark), drivers/mini_writeback_check.py, mini_choose.py
  local-auth fresh profile: $W/scripts/run_la.sh a3_hydration-tp-a3 <dev|prod> ... (drivers/la_storage.py "fresh ..." checks)
EVIDENCE: a3_hydration/NOTES.md §0-§2; results/posctl/f1combo_a1_prod_fresh.json (control catches a1: LS cu_ls,wt_ls,wu_ls,wu_sync; SS cu_ss,wu_ss; cookies cu_ck,wu_ck);
  results/f002/a3_prod_*.json, a3_dev_*.json: fresh x2 dev+prod write nothing (only theme/last_compiled_theme); v1 -> v2 build returning visitor sees all v2 values;
  f1_sync_tabs converges sync-from-tabA with no storage event in A; mini: fresh {} no cookie, returning never-chose sees new default dark, user choice blue +
  consent cookie kept; bootecho fresh `/`, `/plainload`: nothing written in dev, prod, prod+redis (`/onload` writes only its on_load values, as on a2/0.9.12),
  incl. Cookie path/max_age/same_site, sync=True LS, substate, 2 ComponentState instances; hydapp s1b pass dev+prod; reflex-local-auth fresh `/`,
  `/login`, `/protected`, `/need2login`: nothing written (dev, prod, prod+redis); google-auth demo: nothing written.
ROOT_CAUSE_GUESS: fixed by #7460 (a2); #7493 only re-marks browser-PROVIDED values dirty (reflex/state.py:2401, 2420-2422), and a fresh browser provides none.
