ITEM: verify_ent_auth
KIND: verify
REF: A3-10 (a3_ent_auth-3)
TITLE: Enterprise auth + Redis: protected rx.LocalStorage / rx.Cookie / rx.SessionStorage values are overwritten with "" by every client-side navigation (and, for sync=True, by any second open tab without navigating) -- CONFIRMED and broadened; pre-existing, enterprise
SEVERITY: medium
STATUS: confirmed
REGRESSION_VS_0.9.12: no (0.9.12 + a5 identical)
REGRESSION_VS_0.10.0a2: no (a2 + a4 identical)
REPRO: Own app (built from the finding text) prerelease_testing/2026-10-07-a3/a3_ent_auth/verification/app (`vea`): AuthPlugin()
  secure default; Vault(rx.State) with draft=rx.LocalStorage(name="vea_draft", sync=True), plain=rx.LocalStorage(name="vea_plain"),
  ck=rx.Cookie(name="vea_ck"), ss=rx.SessionStorage(name="vea_ss"), protected events fill / show_server (echoes backend values);
  Pub(rx.State) with the same storage kinds as rxe.field(..., auth=False); pages / (auth=False), /vault, /vault2 linked by rx.link.
  Setup + commands: a3_ent_auth/NOTES.md "## VERIFICATION" (ports 3620/8620, prod 8621, redis 8629, mock IdP 8638):
    $W/bin/infra.sh start; redis-cli -p 8629 flushall; VEA_INSTRUMENT=1 $W/bin/start.sh a3-ent vea_a3e dev $W/logs/x.log
    cd $W/drivers; $DRV vea_drv.py storx http://localhost:3620 a3e-dev-redis 1; $DRV vea_drv.py xsync http://localhost:3620 a3e-dev-redis 2
  Results: sign in alice, fill -> click "vault2" link -> draft/plain/ck/ss shown "" and written "" to localStorage/cookie/sessionStorage
  (every nav: /vault->/vault2, /vault2->/vault, /vault->/); show_server right after shows the backend still holds draft-of-alice;
  after a reload the backend holds "" (re-seeded from the browser) -> value lost on both sides. auth=False controls kept.
  xsync (two tabs of one browser, fill in tab A, no navigation): tab A's own sync=True draft becomes "" within ms (storage event ->
  tab B update_vars_internal -> rewritten to "" -> B writes "" -> storage event -> A's update_vars_internal{draft:""}).
  Matrix: a3 dev Redis, a3 prod Redis 1 worker and 9 workers (2/2), 0.9.12 + a5 dev Redis, a2 + a4 dev Redis: all wiped;
  a3 dev disk (the default) and memory: kept. Explorer fixture (vauthx + storx.py copy) on a3 dev Redis: wiped 2/2 at 3c/3d/4.
  Causality: VEA_FIX=1 (AuthMiddleware.preprocess calls resolve_userinfo before update_vars_internal, as it already does for
  hydrate/hydrate_and_load) -> nothing wiped in storx or xsync, tab B receives the synced draft.
  Realistic impact: any enterprise app with AuthPlugin (default protection covers every app state) + Redis (needed for multi-worker
  prod) that keeps preferences/drafts/ids in rx.LocalStorage/rx.Cookie/rx.SessionStorage loses them at the first rx.link navigation;
  sync=True values cannot survive two open tabs. Fails closed (no exposure). Workaround: mark such vars rxe.field(..., auth=False).
EVIDENCE: prerelease_testing/2026-10-07-a3/a3_ent_auth/verification/out/{a3e-dev-redis,a3e-dev-redis-fix,a3e-dev-disk,a3e-dev-memory,a3e-prod-redis-1w,a3e-prod-redis-dw,s912e5-dev-redis,a2e-dev-redis}-{storx,xsync}.json.gz
  (ws frames: nav update_vars_internal carries draft-of-alice, reply delta vault:{draft:"",plain:"",ck:"",ss:""} beside pub unchanged);
  logs/*.trimmed.log (VEA_FILTER ... auth_user=NOT-LOADED(ValueError) changed={'draft_rx_state_': ('draft-of-alice', '')...});
  out_vdrv/a3e-vauthx-dev-redis-storx.json.gz; shots/a3e-dev-redis-storx-0-S1_nav_vault_to_vault2.jpg, *-xsync-0-A1_after_fill_in_A.jpg
ROOT_CAUSE_GUESS: confirmed (reflex-enterprise 0.9.7a5 wheel, byte-identical in a4): auth/enforcement.py AuthMiddleware.preprocess
  1694-1716 returns for exempt states after loading AuthUserState only for hydrate/hydrate_and_load, so reflex's
  UpdateVarsInternalState.update_vars_internal (reflex/state.py:2738 a3; :3070 0.9.12) runs with no AuthUserState in the Redis
  partial tree; filter_protected_delta 1432 -> _auth_user_for_state 848-871 (_get_state_from_cache raises ValueError -> None) ->
  withhold -> _record_withhold replaces with the anonymous placeholder (1484-1490); the browser persists it
  (reflex_base/.templates/web/utils/state.js:1045 applyClientStorageDelta; triggers: compiler/templates.py:364 onLoadInternalEvent on
  every navigation, state.js ~1270 storage event -> update_vars_internal). Same root cause as N-034 (enterprise#263), but here the
  placeholder is persisted -> data loss. Owner: reflex-enterprise (load AuthUserState / resolve the user for update_vars_internal, or
  do not emit placeholders for client-storage keys when the identity is merely unloaded).
