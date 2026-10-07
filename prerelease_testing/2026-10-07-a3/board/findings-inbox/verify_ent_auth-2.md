ITEM: verify_ent_auth
KIND: verify
REF: A3-09 (a3_ent_auth-4)
TITLE: Stale tab signed out by the boot reconcile stays on the protected page blanked -- NARROWED: a3 behaviour confirmed, but 0.9.12's redirect is the winner of a race (app/timing dependent), and live cross-tab logout leaves the page blanked on every version; no exposure; enterprise
SEVERITY: low
STATUS: narrowed
REGRESSION_VS_0.9.12: partial (changed odds of a pre-existing race; not deterministic: 0.9.12 also stays blanked in my app 6/6 dev)
REGRESSION_VS_0.10.0a2: no (a2 never signed the tab out, N-032)
REPRO: Own app `vea` (prerelease_testing/2026-10-07-a3/a3_ent_auth/verification/app) + driver drivers/vea_drv.py; setup in
  a3_ent_auth/NOTES.md "## VERIFICATION":
    $DRV vea_drv.py stale|away|live|stalenav http://localhost:3620 <label> 3 ; $DRV summ.py ../out/<label>-{stale,away,live}.json
  stale = tab1 signed in on /vault goes to same-origin /blank.html, cookies cleared + token hash "" written, tab1 returns to /vault;
  away = tab1 leaves, tab2 logs out (/logout + IdP End session), tab1 Back; live = tab1 stays open while tab2 logs out.
  Explorer fixtures: drivers_explorer_copy/vdrv.py (only IdP port + out dir changed) stale|away on the explorer's vauth app.
  Results (stay = /vault with who="" and every protected value blanked):
    vea a3 dev Redis: stale stay 3/3, away stay 3/3, live stay 3/3.   vea 0.9.12 + a5 dev Redis: stale stay 3/3, away stay 3/3, live 3/3.
    vea a3 prod Redis 1w: stale stay 3/3, away stay 2/3 (/login 1/3). vea 0.9.12 prod 1w: stale stay 1/3 (/login 2/3), away stay 2/3.
    vauth a3 dev Redis: P3 stay 3/3, away stay 3/3, P4 stay 3/3.      vauth 0.9.12 dev Redis: P3 /login 3/3, away /login 3/3, P4 stay 3/3.
  In every stay case: a protected click -> /login in ~0.2 s (vea 18/18, vauth 6/6), a client nav to another protected page -> /login
  (2/2), public events work; nothing protected is rendered after the reset. Pre-existing on both versions: before the reset the boot
  snapshot renders the previous user's protected values briefly (DOM log: a3 dev 6-20 ms, 0.9.12 dev 30-51 ms, prod 19-221 ms both).
  Mechanism (ws frames): on 0.9.12 the cookie-sync POST triggered by update_vars_internal's hash mismatch races the separately sent
  on_load_internal page guard (vauth: POST first -> guard sees no tokens -> /login; vea: guard first -> allowed, then
  reconcile_tokens_after_sync -> reset_auth blanks the page). a3's hydrate_and_load chains on_load_internal server-side, so the guard
  nearly always wins. reset_auth never re-runs the guard, so the live P4 case stays blanked on every version.
  Realistic impact: cosmetic -- a tab whose session was ended elsewhere shows an empty protected page until the next action, which
  lands on /login. No data or action exposed in the blanked state.
EVIDENCE: prerelease_testing/2026-10-07-a3/a3_ent_auth/verification/out/{a3e-dev-redis,s912e5-dev-redis,a3e-prod-redis-1w,s912e5-prod-redis-1w}-{stale,away}.json.gz,
  {a3e,s912e5}-dev-redis-live.json.gz, a3e-dev-redis-stalenav.json.gz, out_vdrv/{a3e,s912e5}-vauth-dev-redis-{stale,away}.json.gz;
  shots/*-stale-*-P_after_boot.jpg, *-away-*-P_after_boot.jpg
ROOT_CAUSE_GUESS: enterprise-owned UX gap: reflex_enterprise 0.9.7a5 auth/oidc/state.py:562 reconcile_tokens_after_sync -> :868
  reset_auth (_reset_session + HTTPCookie.sync(), no redirect / page-guard re-run); the page guard (auth/page_guard.py page_guard ~165)
  runs only on page load. reflex side is intentional ordering: reflex/state.py:2368-2430 hydrate_and_load returns
  [OnLoadInternalState.on_load_internal] (guard before the frontend's cookie sync). Fix: after a reconcile reset on a protected page,
  redirect to login_url_for(current url) (would also fix the live P4 case on all versions).
