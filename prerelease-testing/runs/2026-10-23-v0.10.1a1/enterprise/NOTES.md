# enterprise — reflex-enterprise 0.9.8 on reflex 0.10.1a1 (vs 0.10.0)

Agent notes, written incrementally. SB=/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa.
Fixtures copied to `$SB/apps/enterprise/src` (= `prerelease-testing/fixtures/enterprise`), runtime copies in
`$SB/apps/enterprise/work` (`WORK`), own apps/probes in `$SB/apps/enterprise/own` (copied here as `own/`).
Venvs: `new-ent` (reflex 0.10.1a1 + reflex-base 0.10.1a1 + reflex-enterprise[mcp] 0.9.8 + oidc-provider-mock 0.4.8),
`prev-ent` (reflex 0.10.0 + rxe 0.9.8), `driver` (playwright 1.64.1 + httpx + websockets); built for this item with
`own/build_venvs.sh`: `enterprise-drv` (ENT_DRV: reflex 0.10.1a1 + rxe[mcp] 0.9.8 + playwright 1.63 + pytest),
`enterprise-ctrl-a3` (reflex 0.10.0a3 + rxe 0.9.8: N-032 positive control), `enterprise-ctrl-rxe96` (reflex 0.10.0 +
rxe 0.9.6: N-025 positive control), `enterprise-demo-new` (reflex[db] 0.10.1a1 + rxe[mcp] 0.9.8 + faker/pandas/aiosqlite).
Enterprise demos / upstream test pieces come from the checkout `/home/user/reflex-enterprise` (HEAD d90408b =
r/pre-2026.10.05 @ v0.9.7a4; `git diff v0.9.8 HEAD -- demos` is empty, so the demos equal the v0.9.8 tag), copied by
`grid/bin/fetch_demos.sh` / `auth/a4auth/fetch_upstream.sh` into `$WORK` (never into the repo).

Shell preamble used for every command below:
```
export SB=/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa
export WORK=$SB/apps/enterprise/work ENT_NEW=new-ent ENT_PREV=prev-ent PREV=prev DRV_VENV=driver ENT_DRV=enterprise-drv
F=$SB/apps/enterprise/src; cd $SB
```

## rxe 0.9.8 changelog (what changed in the enterprise package itself)
`git show v0.9.8:CHANGELOG.md`: ONE entry, #277 — OIDC sign-in failing with an app state mismatch when a login was
started twice in the same tab (double click); later starts reuse the tab's pending state/PKCE pair until a callback
consumes them, logout no longer overwrites them, a mismatch restarts the sign-in once and returns to the page the
sign-in started from. Source diff v0.9.7..v0.9.8: only `reflex_enterprise/auth/oidc/state.py` (+ tests).
Tested by `own/probes/pending_login.py` (see below).

## Results

### Static checks (no server)
- `own/probes/import_sweep.py` (`EXPECT_VENV=<v> $SB/envs/<v>/bin/python -I import_sweep.py out.json`): new-ent and
  prev-ent both import 112/113 `reflex_enterprise.*` modules with **0 Python warnings**; the only failure is
  `reflex_enterprise.testing.plugin` (needs `pytest`, same on both). JSON: `own/import_sweep_{new-ent,prev-ent}.json`.
- `own/probes/shims.py` (ENT-01 / ENT-02 / CLI-03, re-verify item 16): `reflex.components.dynamic.bundled_libraries`
  (list), `from reflex.page import DECORATED_PAGES` (defaultdict), `get_config(reload=True)` (Config) all WORK on both
  venvs and each prints its `console.deprecate` line ("deprecated in version 0.9.9 ... removed in 1.0"). rxe 0.9.8 itself
  reads `RegistrationContext.ensure_context().bundled_libraries` first (`reflex_enterprise/vars.py:39`) and only falls
  back to the shim on old reflex, so rxe does not hit the deprecation on 0.10.x. **fixed / unchanged.**

### Auth suite part 1+2 — `auth/bin/seq_ent_auth.sh new-ent new 12` (dev, Redis 8629, mock IdP 8638; output `work/ent-auth-new.txt`)
ENT-30 / N-032 (re-verify item 3), new-ent (reflex 0.10.1a1 + rxe 0.9.8):
- vdrv stale: `{"p1_corrected": 3, "p2_corrected": 3, "p3_logged_out": 3, "p4_logged_out": 3} of 3`
- vdrv away: tab1 logged out after Back **3/3**; vdrv xtab: tab1 logged out **3/3, accepted-after-logout 0/3**
  (race 1/3 = tab1 re-wrote the old hash once, healed by tab2's reconcile — same variance as the 0.10.0 record)
- hunt relogin ok 2/2; server log 0 tracebacks / 0 TypeError. = the fixtures README's 0.10.0 record. **still fixed.**
- Server-log observation (new): 17 vite lines `Files in the public directory are served at the root path. Instead of
  /public/external/reflex_enterprise/components/message_listener/messageListener.js, use /external/...` (Debug level).
  rxe's `auth.jsx` imports `$/public/external/.../messageListener.js` (`rx.asset(..., shared=True).importable_path`,
  identical code on 0.10.0); compared against the prev-ent log below.

### Client IP (#7614) — static reading of rxe 0.9.8 (`git grep` on tag v0.9.8)
- `reflex_enterprise/plugins/event_handler_api.py:1353-1355` (REST `POST /_reflex/event/<state>/<handler>`):
  `client_ip = headers.get("x-forwarded-for", client_ip).partition(",")[0].strip()` — LEFTMOST XFF entry, unconditional,
  becomes `router.session.client_ip` of the token-bound session; `asgi-scope-client` keeps the real peer.
- The rate limiters never use that value: `plugins/rate_limit.py:230 client_ip_from_scope(scope, trusted_proxy_hops)`
  (peer unless hops>0, then the entry `hops` from the RIGHT) keys `POST /_reflex/auth/token` (api_tokens.py:437,
  `EventHandlerAPIPlugin(trusted_proxy_hops=)`), the MCP call limiter (mcp.py:379) and MCP registration
  (`MCPPlugin(registration_trusted_proxy_hops=)`).
- `reflex_enterprise/auth/audit.py` records no IP at all; MCP/agent sessions get `router_data_for_token(...)` whose
  `client_ip` defaults to `"0.0.0.0"` (no XFF). So no rxe-internal security decision keys on the spoofable value; the
  exposure is user code reading `self.router.session.client_ip` in a handler invoked over the REST API.
- End-to-end confirmation: `own/xff_run.sh <venv> <reflex_hops> <label> [ws_version]` (own `hnet` app on 3610/8610 with
  `rxe.EventHandlerAPIPlugin(token_rate_limit=0)`; `own/probes/rest_probe.py` = REST path, `own/probes/ws_probe.py` =
  the hydration_net item's raw websocket client reused unchanged). Results below.
- part 2 (entauth explorer app, dev + Redis): `drive_auth_redis` cycle/pubnav/twotab/xtab **ALL_PASSED**; `xtab_probe`
  **TAB1_LOGGED_OUT 5/5**; `stale_hash_probe` **CORRECTED {"anon_boot": [3,3], "loggedin_boot": [3,3], "live_update": [3,3]}**;
  `hydration_token_probe` SUMMARY `{reload_writes: True, newtab_writes: True, garbage_protected: False, garbage_public: False,
  garbage_id_refresh: False, garbage_all_after_login: True}` (verbatim the 0.10.0 line); server log 0 tracebacks.
  hunt loads per step = record (1 `hydrate_and_load` per boot, `on_load_internal`+`update_vars_internal` on client nav,
  0 idle events, 1 `add_entry`). Browser noise only the known mock-IdP pico.css tunnel failure + cookie-sync keepalive aborts.

### rxe 0.9.8 #277 pending-login — `own/pl_run.sh new-ent new 2 dev` (vauth, dev, Redis; driver `own/probes/pending_login.py`)
Output `own/out/pending_login_new-dev.json`, server log `work/auth/logs/pl-new-dev.server.log`.
- A two_starts (start login twice from /vault→/login, finish the FIRST authorization page): **pass 2/2**, and the two
  authorization URLs carry the SAME `state` (`pair_reused: true`) — the 0.9.8 reuse behaviour.
- B other_tab (tab2 completes tab1's authorization page): rejected (`AuthStateMismatchError` logged with a traceback,
  2 per run = the intended rejection), auto-restarted ONCE with tab2's own pair (`restart_state_is_own: true`), then signed
  in on /vault: **pass 2/2**.
- C real double click on "Login with Generic": **pass 2/2**. E (dev only) a signed-in tab survives a backend hot reload
  (touch vauth.py → "Changes detected, reloading workers" → reload → still alice, protected click works): **pass**.
- D logout_keep failed 0/2 in this run because of a driver bug (a second `go_back()`); fixed and re-run in queue2.
- Browser console: only the known mock-IdP pico.css `ERR_TUNNEL_CONNECTION_FAILED` + its 404.

### Client IP end to end — websocket half (own hnet app, `own/xff_run.sh`; JSON in `own/out/xff_<label>_ws_*.json`)
| run | XFF header sent on the websocket upgrade | `router.session.client_ip` seen by `IPState.rec` |
|---|---|---|
| new-ent, REFLEX_TRUSTED_PROXY_HOPS=0 | none / `6.6.6.6` / `6.6.6.6, 7.7.7.7` | `127.0.0.1` / `127.0.0.1` / `127.0.0.1` (XFF ignored, #7614) |
| new-ent, REFLEX_TRUSTED_PROXY_HOPS=1 | none / `6.6.6.6` / `6.6.6.6, 7.7.7.7` | `127.0.0.1` / `6.6.6.6` / `7.7.7.7` (rightmost = the entry 1 hop from the right) |
| prev-ent (0.10.0, no setting) | none / `6.6.6.6` / `6.6.6.6, 7.7.7.7` | `127.0.0.1` / `6.6.6.6` / `6.6.6.6` (leftmost, spoofable) |
`asgi-scope-client` = 127.0.0.1 in every case; `client_token` (36) / `session_id` (20) present in the handler's router view
as expected. REST half: see below (first attempt failed on the driver venv's httpx 1.0 `base_url` removal; fixed, rerun in queue2).
