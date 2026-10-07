ITEM: a3_ent_auth
KIND: new
REF: -
TITLE: Enterprise auth + Redis: every client-side navigation erases a signed-in user's client-storage vars (rx.LocalStorage / rx.Cookie) on default-protected states — the delta filter fails closed and the browser persists the "" placeholders
SEVERITY: medium
STATUS: new
REGRESSION_VS_0.9.12: no
REGRESSION_VS_0.10.0a2: no
REPRO: |
  App apps/vauthx (prerelease_testing/2026-10-07-a3/a3_ent_auth/apps/vauthx): rxe.App + AuthPlugin() (secure by default),
  state `class Vault(rx.State)` with `draft: str = rx.LocalStorage("", name="vx_draft", sync=True)`,
  `ck: str = rx.Cookie("", name="vx_ck", max_age=3600)`, protected event `set_draft` (sets "draft-of-<sub>"), pages
  / (auth=False), /vault and /vault2 (secure default) with rx.link client-side navigation between them.
  SB=...scratchpad; W=$SB/apps/a3_ent_auth; $W/bin/infra.sh start            # redis :8349 + mock OIDC :8358
  $W/bin/run_storx.sh a3-ent:vauthx_a3e:a3e-dev-redis-v2                       # dev, REFLEX_REDIS_URL set, port 3340
  (manual: sign in as alice on /vault, click "set draft" -> draft-of-alice shown and in localStorage['vx_draft'] + cookie vx_ck;
   click the "vault2" link -> the page shows draft="" and the frontend writes localStorage vx_draft="" and vx_ck="" ; the
   user's value is gone, and the next boot sends "" so the backend loses it too)
  Results (drivers/storx_table.py <label>): client nav /vault -> /vault2 (both protected), /vault2 -> /vault and /vault -> /
  all write "" over alice's values on a3 + a5, a2 + a4 and 0.9.12 + a5 with Redis (2/2 reps each). With the memory state
  manager (NOREDIS=1) on a3 the values survive every navigation. Full reloads / new tabs keep them on a3 and a2 (0.9.12 also
  wipes the LocalStorage value on a new tab's boot).
EVIDENCE: prerelease_testing/2026-10-07-a3/a3_ent_auth/logs/{a3e,a2e,s912e5}-dev-redis-v2-storx.{json.gz,out}, logs/a3e-dev-memory-v2-storx.*, drivers/storx.py, apps/vauthx/
ROOT_CAUSE_GUESS: reflex_enterprise/auth/enforcement.py filter_protected_delta (~1432) resolves the user with _auth_user_for_state -> state._get_state_from_cache(AuthUserState) (~848-871), which returns None when AuthUserState is not loaded in the event's state tree (update_vars_internal under the Redis manager only loads the substates it touches) -> fail closed -> each protected client-storage var is replaced by its anonymous placeholder; the frontend persists client-storage values from any hydrated delta (state.js applyClientStorageDelta), so the placeholder overwrites the browser's copy. Pre-existing enterprise issue; workaround: mark such vars auth=False or load AuthUserState in the event.
