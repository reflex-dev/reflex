ITEM: a3_events_tp
KIND: new
REF: - (side effect of #7493, regression-risk item "extra/duplicate deltas")
TITLE: #7493 brings back 0.9.12's duplicate boot delta: on every page load with a non-default client-storage value, the storage var and every computed var that depends on it are evaluated twice and sent twice (a2: once)
SEVERITY: low
STATUS: changed
REGRESSION_VS_0.9.12: no (0.9.12 does exactly the same: 4 deltas, 2 evaluations per dependent var)
REGRESSION_VS_0.10.0a2: yes (performance only; a2 sent 3 deltas and evaluated each dependent var once; functionality identical)
REPRO: |
  Core-only app prerelease_testing/2026-10-07-a3/a3_events_tp/events/src/bootdup (LocalStorage `tok` (key bd_tok), cached computed vars
  `derived`/`lookup` on it, `sub_derived` in a substate; every evaluation prints `BOOTDUP eval <name> #n`):
    W=<copy of a3_events_tp/events>; bash $W/bin/start.sh a3 dev bd bootdup && bash $W/bin/wait_up.sh http://localhost:3474/
    cd $W/driver && NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python drive_bootdup.py http://localhost:3474 out.json $W/logs/bd.log
    bash $W/bin/stop.sh bd      # same with venv alpha2 / stable, and `prod` (port 8477)
  Per reload with localStorage bd_tok="hello" (3 reloads each):
    a3 dev+prod:     4 deltas, 2 of them carry tok/derived/lookup/sub_derived with identical values; derived, lookup, sub_derived evaluated 2x each
    0.9.12 dev+prod: same as a3
    a2 dev+prod:     3 deltas, 1 carries them; each evaluated 1x
  Fresh profile (nothing stored): no `bd_tok` written to localStorage on any version (F-002 stays fixed); on_load runs once everywhere.
  Real package: reflex-local-auth demo (prod, logged in, /user-info reload; tp/drivers/drive_boot_frames.py ... local): a3's second boot delta
  re-sends `auth_token`, `is_authenticated`, `authenticated_user` (a DB-backed cached var) and `authenticated_user_info`; a2's second delta is
  only `{"is_hydrated": true}`. Magic-link (LocalStorage sync=True): token re-sent in the second delta, but 5 extra tabs cause 0 frames in the
  first tab and 0 idle frames (no sync echo/storm), same as a2.
EVIDENCE: a3_events_tp/events/out/bootdup/bootdup_{a3,alpha2,stable}_{dev,prod}.json (+ logs/bootdup_*.log); a3_events_tp/tp/out/boot/{local,magic}-{all,a2}-prod.json (`loads[1].all_frames`)
ROOT_CAUSE_GUESS: intended by #7493 (client-storage vars re-marked dirty after the guarded snapshot in hydrate_and_load, so the final boot delta goes through get_delta overrides); the re-marked var also dirties its dependent computed vars, which are recomputed and re-sent although the first delta already carried them. Cost per page load = one extra evaluation of every storage-dependent computed var (e.g. reflex-local-auth's `authenticated_user` session query) plus a duplicate delta. Not a blocker; worth a follow-up if the a2 single-delta behaviour can be kept while still routing storage vars through get_delta.
