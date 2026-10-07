# Cluster `ent_auth` — enterprise OIDC / MCP / maps on reflex 0.10.0a2 + offline reflex-enterprise 0.9.7a4

Status: COMPLETE (2026-10-07 ~12:40 UTC). Section "Results" at the end is the summary; issue write-ups follow it.
Log files larger than 40 KB are stored gzipped in `logs/` (`foo.json` → `foo.json.gz`); the names below omit `.gz`.

This cluster was resumed from a previous agent that was cut off by a spend limit. Its evidence
(xtab cross-tab-logout matrix, first `drive_auth_redis.py` run) was kept in `logs/` and is analysed
here, not re-run; everything else below was run in this pass.

## Environment

- Machine: Linux x86_64, 4 CPU, shared with 3 other agents (load 2-6 during the runs).
- Packages under test: `reflex==0.10.0a2` (+ the whole 0.10.0a2 train) and the user-supplied
  OFFLINE wheel `reflex_enterprise-0.9.7a4-py3-none-any.whl` (`$SB/downloads/enterprise_wheel/`),
  installed by file path. Nothing installed from the checkouts, nothing from `reflex-enterprise` on PyPI.
- `SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad`
- Venvs (all Python 3.12):
  - `$SB/envs/alpha2-ent` (shared, read-only): `reflex[db]==0.10.0a2` + wheel `[mcp]` + `oidc-provider-mock 0.4.8` + `greenlet` (N-001 workaround added by the orchestrator).
  - `$SB/envs/ent_auth2-drv`: same graph as alpha2-ent plus `playwright==1.63.0` (MCP OAuth driver needs `mcp` + playwright in one interpreter).
  - `$SB/envs/ent_auth2-a1w`: `reflex[db]==0.10.0a1` + wheel `[mcp]` + `greenlet` (pins: `logs/pins-a1.txt`, install log `logs/venv-a1w.log`).
  - `$SB/envs/ent_auth2-s912w`: `reflex[db]==0.9.12` + wheel `[mcp]` + `greenlet` (pins: `logs/pins-s912.txt`, `logs/venv-s912w.log`).
  - `$SB/envs/driver` (shared): playwright 1.63 + httpx, Chromium `/opt/pw-browsers/chromium`.

  Recreate a baseline venv (greenlet is REQUIRED for any `reflex[db]` venv: N-001):
  ```sh
  cd $SB && uv --no-config venv --python 3.12 $SB/envs/ent_auth2-s912w
  cd $SB && uv --no-config pip install --python $SB/envs/ent_auth2-s912w/bin/python --prerelease=allow \
      'reflex[db]==0.9.12' "$SB/downloads/enterprise_wheel/reflex_enterprise-0.9.7a4-py3-none-any.whl[mcp]" \
      'pydantic<2.14' greenlet
  # a1: same with 'reflex[db]==0.10.0a1'; drv: same with 'reflex[db]==0.10.0a2' playwright==1.63.0
  ```
- Ports (reserved range): app dev 3340/8340, prod single port 8341, a4 full auth app 3342/8342,
  a4 auth_min 3343/8343, maps dev 3344/8344, maps prod 8345, redis 8349, mock OIDC 8358.

## Apps

- `apps/entauth/` — enterprise OIDC + MCP test app (FlowState/OrgState = upstream AuthFlowApp body;
  ListBase/ListWorker = protected background task mutating an inherited list; PidState; AgentState
  for MCP). Env knobs in `rxconfig.py` (AUTH_EXTRA_SCOPES, AUTH_MULTI, MCP_*). `entauth_a1/` and
  `entauth_s912/` in the work dir are byte-identical copies used for the baselines (own `.web`).
- `apps/a4auth/` — the 10-05 a4 auth matrix (apps `auth`, `auth_min`, `components`, drivers
  `drive_auth.py` (22 cases), `recheck_reload.py`, `drive_auth_min.py`, `recheck_iframe.py`,
  `check_mcp*.py`), re-pointed to ports 3342/8342 and 3343/8343 and the local Chromium.
- `apps/mapsapp/` — `rxe.map` app: draggable marker -> State, layers control, geolocation, 200
  circle markers from a State list rotated by a background task every second.

## Infrastructure commands

```sh
W=$SB/apps/ent_auth2            # the work dir (copied here as apps/ + scripts/)
$W/scripts/infra.sh start       # redis-server :8349 + scripts/mock_oidc.py (oidc-provider-mock) :8358
# app (dev, Redis):  VENV=alpha2-ent APP_DIR=entauth $W/scripts/start_app.sh dev $W/logs/<log>
# app (prod, Redis): VENV=alpha2-ent APP_DIR=entauth APP_BP=8341 $W/scripts/start_app.sh prod $W/logs/<log>
$W/scripts/wait_ready.sh http://localhost:3340/ http://localhost:8340 360
$W/scripts/stop_app.sh          # kills the process group, then any leftover listener in 3340-3359/8340-8357
$W/scripts/infra.sh stop
```
`run_app.sh` exports `CI=true REFLEX_TELEMETRY_ENABLED=false OIDC_ISSUER_URI=http://localhost:8358
OIDC_CLIENT_ID=reflex-integration-test OIDC_CLIENT_SECRET=reflex-integration-test-secret
AUTHLIB_INSECURE_TRANSPORT=1 REFLEX_REDIS_URL=redis://localhost:8349` (REDIS=0 for the memory manager).
Drivers run as `NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python <driver> ...`
from `$W/scripts` (MCP drivers: `$SB/envs/ent_auth2-drv/bin/python`).

## 1. OIDC on Redis (dev) — first pass (previous agent, evidence kept)

`scripts/drive_auth_redis.py http://localhost:3340 a2-dev-redis` (cases cycle, pubnav, twotab, xtab) →
`logs/drive-auth-a2-dev-redis.out`, `logs/auth-a2-dev-redis.json`, `screenshots/a2-dev-redis-*.png`,
server log `logs/entauth-dev-redis-a2.log`.

- cycle: Alice login → reveal / async admin / admin events → reload (values from Redis) → /list
  background task appends to the INHERITED list → reload shows `alice-bg-0..4` (the #7312 fix; on
  0.9.12 the same task's list mutation is lost, see §3) → public nav + reload keeps protected sync/async
  computed vars (#252) → logout via IdP end_session (UI reset to placeholders, no oidc cookies) → Bob on
  the same browser sees none of Alice's data, his own bg items, no `alice` in storage or in any Redis key
  of his token. PASS.
- pubnav: protected computed vars after public navigation + 2 reloads in a fresh context. PASS.
- twotab / xtab: see §2 — the second tab is NOT logged out (`tab1_after_tab2_logout: stayed ... secret=revealed-alice`).
- Anomaly: background task on a protected state does not update the page live (§3).
- Benign request noise: `pico.min.css` from cdn.jsdelivr.net (ERR_TUNNEL_CONNECTION_FAILED, sandbox
  proxy; it is the mock IdP's stylesheet), `/_reflex/cookies/sync` ERR_ABORTED (navigation aborts the
  keepalive POST; also recorded on a1 10-05 and on 0.9.12), console 404 / tunnel errors on
  `localhost:8358/oauth2/authorize` (mock IdP favicon + pico css).

## 2. Cross-tab logout is unreliable on 0.10.x (REGRESSION vs 0.9.12 + same wheel)

Scenario (`scripts/xtab_probe.py <base> <label> <N>`, instrumentation `scripts/instrument.py`): one
browser context; tab1 logs in as Alice on `/list`; tab2 opens `/dashboard` (same cookies, own client
token); tab2 clicks logout → IdP end_session → back on `/` anonymous. After 6 s tab1 should be logged
out (0.9.12 behaviour): its protected click / reload must land on `/login`.

| combination (dev) | tab1 logged out | evidence |
|---|---|---|
| reflex 0.9.12 + wheel, Redis | **6/6** | `logs/xtab-s912w-dev-redis.json`, `logs/xtab-s912w-rep-{0..4}.json`, `-summary.json` |
| reflex 0.10.0a1 + wheel, Redis | **2/6** | `logs/xtab-a1w-dev-redis.json`, `logs/xtab-a1w-rep-*.json` |
| reflex 0.10.0a2 + wheel, Redis | **3/7** (+ 0/2 in `drive_auth_redis` twotab/xtab) | `logs/xtab-a2-dev-redis*.json` |
| reflex 0.10.0a2 + wheel, memory manager | **3/5** | `logs/xtab-a2mem-rep-*.json` |

When it fails, tab1 keeps working as Alice indefinitely: protected events still run (`add_item`
appended `manual`), a reload of tab1 stays on `/list` as `alice` (its server-side session in Redis still
holds the tokens), although the browser has no oidc cookies left and the IdP session is ended. A NEW tab
correctly lands on `/login`.

Mechanism (event timelines in the per-run JSON `events`; compare `xtab-s912w-rep-0.json` with
`xtab-a2-dev-redis-rep-0.json`): tab2's logout writes `latest_access_token_hash_ls=""` → tab1 gets the
storage event → tab1 runs `HTTPCookie.sync` + `reconcile_tokens_after_sync`. If tab1's cookie-sync POST
leaves before tab2's cookie-clearing response lands (a race that happens on BOTH versions), tab1 still
sees the old cookies, re-adopts them and writes its OLD hash back to localStorage. On 0.9.12 this is
self-healing: when tab2 returns from end_session it boots with `hydrate` + `update_vars_internal`; the
latter's delta goes through `OIDCAuthState.get_delta` → `_handle_latest_access_token_hash_ls_in_delta`,
which sees the stale hash ≠ its own (""), queues `HTTPCookie.sync(reconcile_tokens_after_sync)`, writes
`""` again and tab1 is logged out on the second storage event. On 0.10.x the boot is one
`hydrate_and_load` event (#7064, a1) that applies client-storage vars, calls `self._clean()` and emits
`self.dict()` — the state's `get_delta()` override is never consulted, so no reconciliation happens at
boot and the stale hash is just echoed back (`is_hydrated=false` delta).

Deterministic root-cause probe `scripts/stale_hash_probe.py <base> <label> <N>`: put a bogus value in
`localStorage[...generic_oidc_auth_state.latest_access_token_hash_ls_rx_state_]` and reload.

| case | 0.9.12 + wheel | 0.10.0a1 + wheel | 0.10.0a2 + wheel |
|---|---|---|---|
| anonymous tab boots with bogus hash → backend rewrites it to "" | 2/2 (sent: hydrate, update_vars_internal, reconcile_tokens_after_sync) | 0/2 (sent: hydrate_and_load only; bogus value kept) | 0/3 |
| logged-in tab boots with bogus hash → reconcile re-asserts the real hash | 2/2 | 0/2 | 0/3 |
| control: bogus hash arrives by storage event (no reload) → corrected | 2/2 | 2/2 | 3/3 |

Logs: `logs/stalehash-{s912w,a1w,a2}-dev-redis.{out,json}`.

## 3. Background task on a protected state: no live UI updates (pre-existing, both versions)

`scripts/bglive_probe.py <base> <label>` (cases nav / direct / navback): Alice on `/list` clicks `fill`
(`ListWorker.fill`, `@rxe.event(background=True)`, appends 5 items to the inherited protected
`ListBase.items` and bumps `progress`). Samples the page for 5 s, then reloads.

| | live during task | after reload | websocket deltas during the task |
|---|---|---|---|
| 0.10.0a2 + wheel (Redis, dev) | NO (3/3 cases): `progress` stays 0, `item_count` flips 0 → **-1** (its `initial_value`), list empty | items 5, progress 5 (persisted) | `{"items": [], "item_count": -1, "progress": 0}` ×6 — every protected value replaced by its anonymous placeholder |
| 0.9.12 + wheel (Redis, dev) | NO (3/3) | progress 5 but **items 0 / item_count 0** (inherited-list mutation lost — the bug #7312 fixed) | `{"progress": 0}` ×6 |

So the enterprise auth filter withholds protected values from every background-task delta even though
the task itself resolves the user (`auth_user.userinfo["sub"]` = alice, items are `alice-bg-*`). Not a
regression (0.9.12 behaves the same); a2's only difference is cosmetic (`item_count` shows its `-1`
placeholder instead of not being sent). The persistence half is a verified improvement (#7312).
Logs: `logs/bglive-{a2,s912w}-dev-redis.{out,json}`, screenshots `*-bglive-*.png`.

## 4. Client-storage / token-cookie writes during hydration (#7460 × enterprise auth)

`scripts/hydration_token_probe.py <base> <label> [scenarios]` (instrumented storage/cookie writes):

| scenario | 0.10.0a2 dev | 0.9.12 dev |
|---|---|---|
| reload_writes: login, reload ×2, public nav + reload, client nav back — any EMPTY `latest_access_token_hash_ls` write or token-cookie deletion while logged in? | none (pass) | none (pass) |
| newtab_writes: tab1 /list, tab2 `/`, tab3 /dashboard — empty-hash writes / storage events reaching the logged-in tabs? | none; tab1 still authorized (pass) | none (pass) |
| garbage_protected: fresh browser with garbage access/id/refresh cookies (same CHIPS attributes as the real ones) → /dashboard | /login; garbage cookies left in place; no cookie sync | identical |
| garbage_public: same cookies → `/` → protected click | anonymous on `/`, click → /login; cookies left | identical |
| garbage_id_refresh: valid login, overwrite id_token cookie, reload | stays Alice (server-side session holds the valid tokens; browser cookies are only read on a sync) | identical |
| garbage_all_after_login: overwrite all 3 token cookies, reload | stays Alice | identical |

No #7460-related regression: a protected page load never wrote an empty/default hash or deleted a
token cookie. Injected cookies are never consulted at boot on either version (by design: HttpOnly
cookies reach the backend only via `/_reflex/cookies/sync`). The "computed var invalidates a bad token
during hydration" path is exercised for real in §5 (provider restart / revocation → userinfo 401).
(The `ok=False` flags printed for the garbage_* scenarios are the probe's over-strict expectation that
cookies get cleared; behaviour is identical on 0.9.12.) Logs: `logs/hydtoken-*.{out,json}`.

## 6. MCP on Redis (dev)

`scripts/check_mcp_anon.py http://localhost:8340 a2-dev-redis --rate` and
`scripts/check_mcp_oauth_redis.py http://localhost:8340 http://localhost:3340 a2-dev-redis`
(run with `$SB/envs/ent_auth2-drv/bin/python`). Results identical to the 10-06 a1 partial run
(`prerelease_testing/2026-10-06/ent_auth_mcp_redis/partial/logs/mcp-*-dev-redis.json`):

- anonymous: no bearer → 401 with `WWW-Authenticate ... resource_metadata=...`; `/_reflex/mcp` (no slash)
  → 307 in dev; tools `search_events/queue_event/get_pending_updates`; bump 4 → count 4 / doubled 8;
  multi-yield handler → `[0,1,2,3]`; background tool `start_bg` returns after the task finished
  (`bg_progress 5, bg_done true`, 1.5 s); upload ticket flow (200, `a.txt:5,b.bin:1234`), ticket replay /
  no ticket → 401; protected handler on anonymous session → explicit error; protected resource → error;
  protected field reads return the redacted default; root `client_token` blanked; per-handler
  `rate_limit=3` → 4th call "Rate limit exceeded"; call rate limit: 61st read refused; token grants:
  429 `rate_limited` with `Retry-After: 55` after 10/min.
- parallel: two MCP sessions × 20 concurrent `bump` on the SAME Redis state → count exactly 40, no errors
  (0.51 s) — no lost updates under lock contention.
- OAuth: metadata/PRM, registration (invalid scope → 400), partial consent (unchecked `items:write` →
  granted `profile:read`), consent deny → `access_denied`, IdP deny → enterprise error page, exchange,
  whoami as alice, protected resource, background tool (30 steps, 9.1 s), hammer +30, refresh (rotation),
  refresh replay → 400, revoke → 401, old access token after refresh → 401.
- Anomaly (both a1 and a2): a handler denied by a token-scope check (`scoped_write` needs `items:write`,
  token has only `profile:read`) returns SUCCESS with an empty delta (`{"is_error": false, "delta": {}}`)
  — the MCP client is not told the call was refused.
- Server log noise: anonymous read of the protected resource logs an ERROR with a full traceback
  (`Error reading resource ... requires an authenticated session`) — the client gets a clean error.

## 5. Token expiry / revocation / provider restart (dev, Redis)

`scripts/expiry_matrix.sh <venv> <appdir> <label> <scenario...>` restarts the mock IdP with the
scenario's token lifetime, THEN restarts the app, then runs `scripts/drive_expiry.py` for that scenario
(`EXPIRY_MOCK_EXTERNAL=1`). The restart order matters — see "JWKS" below; the first attempt without it is
kept as `logs/expiry-a2-dev-redis-jwks-cached-attempt.out` (every login failed).

| scenario | 0.10.0a2 + wheel | 0.9.12 + wheel |
|---|---|---|
| proactive: 75 s tokens with refresh token, idle 120 s | refreshed in the background (mock log: token+userinfo at +24 s and +95 s), still Alice, protected event allowed, reload OK | (not re-run) |
| expire_norefresh: 30 s token, NO refresh token, idle 40 s, then protected event | **still logged in, protected event ALLOWED** (no redirect, no error) | identical |
| expire_closed_tab: 40 s tokens, tab closed 50 s, new tab → /dashboard | logged in (new tab's cookie sync refreshed the token: 2nd token+userinfo in mock log) | (not re-run) |
| revoke: `POST /users/alice/revoke-tokens` at the IdP (204) | protected event still allowed, reload still logged in; `force_refresh` → refresh 400 `invalid_grant` → "resetting auth (user will be logged out)" but the page stays on /dashboard until the next reload → /login | identical |
| restart_provider: IdP restarted (new signing key, empty token store) | existing session keeps working (reveal allowed); refresh → 400 → reset; **a fresh login after the restart fails** silently back to "Sign in" | identical |

Observations (all pre-existing, enterprise-side, identical on 0.9.12 → not regressions):
- An expired access token without a refresh token keeps authorizing protected events: the session is
  not re-validated until the userinfo cache (`USERINFO_CACHE_INTERVAL = 1800 s`) lapses. IdP-side
  revocation is likewise only noticed at the next refresh.
- JWKS is cached for the app process lifetime: after the IdP rotates its signing key (here: restart of
  the mock), every new login fails with `InvalidKeyIdError: No key for kid ...` → "Tokens failed
  validation immediately after the exchange; resetting session (user will NOT be logged in)" (server
  log `logs/entauth-dev-redis-a2-dev-redis-expiry-restart_provider.log`, also `logs/entauth-dev-redis-a2-p3.log`).
  The user just lands back on "Sign in" with no message. Only an app restart recovers. Real IdPs rotate
  keys, so this is worth an enterprise ticket (unknown-`kid` → refetch JWKS).
- No tracebacks reach the browser in any scenario; server logs carry ERROR+traceback for the refresh
  400 and the kid failure.
Logs: `logs/expiry-{a2,s912w}-dev-redis*.{out,json}`, `logs/mock-oidc-*-<scenario>.log`,
`logs/entauth-dev-redis-*-expiry-<scenario>.log`.

## 7. PROD (single port 8341, Redis): multi-worker cookie sync 405 (pre-existing, enterprise)

`reflex run --env prod` with `REFLEX_REDIS_URL` spawns **9 granian workers** on this 4-CPU box
(`(cpu_count*2)+1`, same default on 0.9.12, 0.10.0a1, 0.10.0a2; log `logs/entauth-prod-redis-a2-9w.log`:
"Spawning worker-1 … worker-9").

- `POST /_reflex/cookies/sync` answers **405 Method Not Allowed** on most workers and 400/200 on
  others: 18 identical curl POSTs → mix of 405/400 on a2, all 405 on a fresh 0.9.12 server.
  Cause (wheel source `reflex_enterprise/auth/cookie.py`): `HTTPCookie.ensure_handlers_registered()`
  inserts the `/_reflex/cookies/sync` route LAZILY, the first time a process builds an
  `HTTPCookie.sync()` event; a worker that has not done that yet falls through to the static-file app (405).
- Browser effect (`scripts/prod_sync_probe.py <base> <label> N`, fresh context per attempt): login itself
  "works" (the tab's server-side session holds the tokens) but the token cookies are never written in
  most attempts: a2 3/4 attempts sync=405 → no `_oidc_*` cookies; 0.9.12 3/4 the same. Consequences: a
  new tab / new window is logged out, cross-tab hash/cookie reconciliation cannot work, refreshed tokens
  are never persisted to the browser.
- Not a regression (0.9.12 + wheel identical: `logs/prodsync-s912w-prod-redis-9w.out`), but every
  production enterprise-auth deployment with Redis (= multi-worker by default) is affected.
- Repro: `infra.sh start`; `VENV=alpha2-ent APP_DIR=entauth APP_BP=8341 scripts/start_app.sh prod logs/x.log`;
  `for i in $(seq 18); do curl -s --noproxy '*' -o /dev/null -w '%{http_code} ' -X POST http://localhost:8341/_reflex/cookies/sync -H 'Content-Type: application/json' -d '{}'; done`
  (expect 400 "No client token in request" from every worker; observed mostly 405).
- Prod also 307-redirects `/dashboard` → `/dashboard/` (all versions); the first prod driver run failed
  only on exact-URL waits (`logs/drive-auth-a2-prod-redis-9w-exacturl.out`) — drivers now accept the slash.

The rest of the prod suite therefore runs with `GRANIAN_WORKERS=1` (honoured by `reflex/utils/exec.py`)
so that it tests the framework rather than this enterprise bug.

## 8. PROD suite on 0.10.0a2 (single port 8341, Redis, `GRANIAN_WORKERS=1`)

`GRANIAN_WORKERS=1 scripts/prod_suite.sh alpha2-ent entauth a2-prod-redis` → `logs/prod-suite-a2.out`
(server log `logs/entauth-prod-redis-a2-prod-redis.log`, prod build by vite 8 in ~5 s):

| check | result |
|---|---|
| `drive_auth_redis.py` cycle (Alice → protected events → reload → bg list persisted → public nav + reload with protected sync/async computed vars → logout → Bob, no Alice data in page/storage/Redis) | PASS (`logs/drive-auth-a2-prod-redis.out`, `logs/auth-a2-prod-redis.json`) |
| pubnav (#252 under Redis, 2 reloads) | PASS |
| twotab / xtab | tab1 NOT logged out after tab2 logout (same regression as §2) |
| `xtab_probe.py` ×5 | tab1 logged out **3/5** (`logs/xtab-a2-prod-redis-rep-*.json`) |
| `stale_hash_probe.py` ×2 | boot corrections 0/2 + 0/2, live-update control 2/2 (same as dev) |
| `hydration_token_probe.py` reload_writes / newtab_writes | PASS — no empty hash writes, no token cookie deletions |
| `bglive_probe.py` direct | not live (same as dev, §3) |
| MCP OAuth + anonymous (`/_reflex/mcp/`) | identical to dev except the no-slash `/_reflex/mcp` → 405 in prod (known/deferred; dev 307). Rate limits, upload tickets, 2×20 parallel bumps = 40, scope-denied handler silently "succeeds" (as in dev) |
| console | only the benign `/favicon.ico` 404 (app has no favicon), mock IdP pico.css tunnel errors, keepalive cookie-sync ERR_ABORTED on navigation |

Extra-scopes variant (`AUTH_EXTRA_SCOPES=1` → `AuthPlugin(extra_scopes=["offline_access","address"])`),
`drive_auth_redis.py ... extrascope`: authorize request carries `scope=openid+email+profile+offline_access+address`,
login, `force_refresh` → "refreshed", reload keeps Alice — PASS in dev (`logs/drive-auth-a2-dev-redis-extrascope.out`)
and prod (`logs/drive-auth-a2-prod-redis-extrascope.out`).

Background-task workaround (§3): after these prod/dev runs the app got `ListWorker.fill_loaded`
(`scripts/patch_bgloaded.py`), which calls `await self.get_state(AuthUserState)` inside EVERY
`async with self:` block. With that, protected background deltas ARE delivered live (progress 0→2/3→5
within 1 s) in dev and prod (`logs/bglive-a2-{dev,prod}-redis-loaded.out`), while the plain `fill`
still is not. So the enterprise delta filter only sees the user when `AuthUserState` happens to be
loaded in the background task's state tree (`_userinfo_for_state` → "None when … the substate is not
loaded"). `apps/entauth/` in DEST contains this patched version; the version used for every earlier run is
`apps/entauth_original_entauth.py.txt` (identical except for `fill_loaded` + its button).

MCP with the DEFAULT 9 prod workers (Redis), `check_mcp_anon.py http://localhost:8341 a2-prod-redis-9w`
(`logs/mcp-anon-a2-prod-redis-9w.{out,json}`): identical to the 1-worker run — sessions, background tool,
upload ticket (200), per-handler rate limit (3 then refused), 2×20 parallel bumps = exactly 40. MCP is
not affected by the lazy-route problem above (its routes are registered at app build).

## 9. Previous campaign's auth matrix (10-05 a4 drivers) on 0.10.0a2 + offline wheel

`scripts/a4_matrix.sh ent_auth2-drv a2` (dev, memory state manager, as on 10-05; mock IdP on 8358; the
servers ran from `ent_auth2-drv` = the alpha2 graph + playwright). Results under `apps/a4auth/logs/a2/`.

| part | 0.10.0a2 | a1 (10-05 record) |
|---|---|---|
| full upstream auth app, 22 browser cases (`drive_auth.py`) | **22/22** | 22/22 |
| focused public nav + 2 reloads (`recheck_reload.py`) | **3/3** | 3/3 |
| `auth_min` default `AuthPlugin` (`drive_auth_min.py`) | **4/4** | 4/4 |
| `auth_min` `AUTH_TEST_EXTRA_SCOPES=1` | **4/4** | 4/4 |
| default-scope iframe pending replay (`recheck_iframe.py`) | **3/3** | 3/3 |
| **total** | **36/36** | 36/36 |
| MCP OAuth (`check_mcp_oauth.py`: discovery, registration, browser consent, PKCE, protected event, code replay, refresh rotation) | pass | pass |
| anonymous MCP (`check_mcp.py`, components app backend-only :8346) | pass | pass |

0 page errors, 0 HTTP errors in every matrix; console errors are only the mock IdP's (pico.css tunnel,
favicon 404); failed requests are the known cookie-sync keepalive `ERR_ABORTED` (21/10/11, same order as
10-05's 21/9/10) and 2 dev route-module aborts. No `Traceback` in any server log.
Harness note: `reflex run --backend-only` refuses to start when `rxconfig.py` sets `frontend_port`
("Cannot specify --frontend-port when not running frontend.") — same on 0.9.12, so the components
rxconfig simply has no frontend_port.

## 10. Maps (`apps/mapsapp`, `scripts/drive_maps.py <base> <label>`)

Dev 3344/8344 and PROD 8345 (default 9 workers), both with Redis; baseline 0.9.12 + wheel dev.

| check | a2 dev | a2 prod (9 workers) | 0.9.12 dev |
|---|---|---|---|
| 200 `circle_marker`s from `rx.foreach` over a State list | pass | pass | pass |
| drag marker → `dragend` → State (`last_drag` = new lat/lng; marker stays where dropped; second drag) | pass | pass | pass |
| no-arg `dragend` handler, marker `on_click` | pass | pass | pass |
| background task rotates all 200 markers every 1 s for 8 s: tick 1..8 live, 8 distinct path geometries, always 200 paths, 0 long tasks | pass | pass | pass |
| drag while the ticker runs; reload restores tick=16 + dragged position | pass | pass | pass |
| `rxe.map.layers_control` renders | pass | pass | pass |
| base layer switch OSM ↔ Topo and overlay circle toggle, driven from State (`rx.cond`) + reload | pass | pass | pass |
| `on_layeradd` fires when a layer is added | **no** (no websocket event at all) | **no** | **no** |
| geolocation denied (`permissions=[]`) → `on_locationerror` "code=1 … User denied Geolocation." | pass | pass | pass |
| geolocation granted → `on_locationfound` 48.8566,2.3522 | pass | pass | pass |
| total | 16/17 | 16/17 | 16/17 |

Logs `logs/maps-{a2-dev-redis,a2-prod-redis,s912w-dev-redis}.{out,json}`, screenshots `*-maps-*.png`.
Observations (all pre-existing, enterprise side):
- `LayersControl.BaseLayer` / `.Overlay` are not exposed by `rxe.map` (`layers_control_base_layer` is
  commented out, "will be implemented in a future update"). Using the importable classes
  (`reflex_enterprise.components.map.controls.LayersControlBaseLayer`) compiles to
  `const LayersControl.BaseLayer = ClientSide(...)` — invalid JS — and in dev EVERY route then 500s
  (vite transform error, `logs/maps-dev-redis-a2.log` first start). Identical codegen on 0.9.12, 0.10.0a1,
  0.10.0a2: `scripts/layers_dynimport_check.py` → `logs/layers-dynimport-check.out`. The original page is
  kept as `apps/mapsapp_with_baselayers.py.txt`.
- `on_layeradd` / `on_layerremove` (MapConsumer → Leaflet `layeradd`) never reach the backend
  (`scripts/layeradd_debug.py`, `logs/layeradd-debug-a2-dev.out`): only `set_base` is sent.
- `rxe.map(id=...)` does not set a DOM id on the Leaflet container (the id keys the JS map ref used by
  `rxe.map.api(id)`), so page tests must select `.leaflet-container`.
- External tiles are blocked by the sandbox proxy (ERR_TUNNEL_CONNECTION_FAILED) — tile `<img>` src
  switching is what is asserted.
- After the broken first start, the next dev start served `504 Outdated Optimize Dep` once (vite
  dep-optimizer refresh after the failed scan) — normal vite dev behaviour, gone on reload.

## Misc observations

- `[ERROR] Unexpected exit from worker-1` is printed by granian on every Ctrl-C/SIGINT shutdown, on
  0.9.12 as well — shutdown noise.
- The previous agent's processes (pids in `pids.txt`) were already gone (machine restarted); all
  ports in 3340-3359/8340-8359 were free at start.
- `logs/` files larger than 40 KB are stored gzipped in this directory (`zcat`).

## Results

PASS
- OIDC on Redis dev + prod(1 worker): login, protected events (sync/async auth checks), reload from Redis,
  inherited-list background mutation persisted (#7312), public nav + reloads keep protected sync/async
  computed vars (#252), logout via end_session, Bob after Alice with no leak in page/storage/Redis.
- extra_scopes (offline_access, address) dev + prod: scope sent, refresh works.
- #7460 × enterprise auth: no empty/default token hash written, no token cookie deleted on any protected
  page load / reload / new tab (dev + prod).
- MCP anonymous + OAuth on Redis dev, prod 1 worker, prod 9 workers; parallel sessions; background tool;
  rate limits; uploads; consent/IdP deny; refresh/revoke.
- 10-05 a4 auth matrix: 36/36 + both MCP checks.
- Maps dev + prod: 16/17 (the one miss is pre-existing).
- Proactive token refresh with 75 s tokens.

FAIL / ANOMALY
- REGRESSION (since 0.10.0a1, still in a2): cross-tab logout unreliable; boot hydration skips the
  enterprise hash reconciliation (§2).
- Pre-existing (0.9.12 identical): prod multi-worker cookie-sync 405 (§7); background-task deltas on
  protected states withheld (§3, workaround: load AuthUserState in every `async with self`); expired /
  revoked tokens keep authorizing until userinfo cache/refresh (§5); IdP key rotation breaks all logins
  until app restart (§5); scope-denied MCP handler reports success (§6); maps LayersControl base/overlay
  unusable + `on_layeradd` never fires (§10).

## Not covered
- Two-provider (`AUTH_MULTI=1`) variant; iframe flows only via the a4 drivers (dev).
- Prod run of the a4 matrix (only the entauth suite ran in prod).
- Redis restart mid-session (F-017 territory).

## Issues (reproduction)

Common setup for all repros (paths are hardcoded in the scripts: `W` in `scripts/common.py`,
`scripts/*.sh`; to rerun elsewhere copy `apps/entauth`, `apps/mapsapp` and `scripts/` into
`$SB/apps/ent_auth2/` or edit `W`):
```sh
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/ent_auth2
$W/scripts/infra.sh start                                   # redis :8349 + mock IdP :8358
VENV=alpha2-ent APP_DIR=entauth $W/scripts/start_app.sh dev $W/logs/repro.log
$W/scripts/wait_ready.sh http://localhost:3340/ http://localhost:8340 360
cd $W/scripts; export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1; PY=$SB/envs/driver/bin/python
# baselines: VENV=ent_auth2-s912w APP_DIR=entauth_s912 / VENV=ent_auth2-a1w APP_DIR=entauth_a1 (identical copies)
```

### I-1 (HIGH, REGRESSION since 0.10.0a1): logging out in one tab leaves the user's other open tabs signed in
- `$PY xtab_probe.py http://localhost:3340 a2 5` → `TAB1_LOGGED_OUT 3 / 5` (a1: 2/6, 0.9.12: 6/6).
- Deterministic: `$PY stale_hash_probe.py http://localhost:3340 a2 3` →
  `CORRECTED {"anon_boot": [0, 3], "loggedin_boot": [0, 3], "live_update": [3, 3]}`; 0.9.12 gives
  `[2, 2], [2, 2], [2, 2]`.
- Manual: tab 1 → http://localhost:3340/list, "Login with Generic", pick alice. Tab 2 (same window) →
  /dashboard, click "logout", "End session". Back in tab 1 wait 6 s, click "add": a `manual` item is
  appended (protected event ran) and a reload of tab 1 still shows `alice`, although the browser has no
  `_oidc_*` cookies and the IdP session is gone. On 0.9.12 tab 1 lands on /login.
- Cause: #7064's single `hydrate_and_load` boot event applies client-storage vars, `_clean()`s and emits
  `dict()`; enterprise `OIDCAuthState.get_delta` (`_handle_latest_access_token_hash_ls_in_delta`, which
  turns a stale `latest_access_token_hash_ls` into `HTTPCookie.sync(reconcile_tokens_after_sync)`) is no
  longer consulted at boot. 0.9.12's separate `update_vars_internal` went through `get_delta`. Same in prod.
- Evidence: `logs/xtab-*.json[.gz]` (event timelines: compare `xtab-s912w-rep-0` with `xtab-a2-dev-redis-rep-0`),
  `logs/stalehash-*.out`, `logs/drive-auth-a2-{dev,prod}-redis.out` (twotab/xtab "stayed").

### I-2 (HIGH impact, NOT a regression): prod with Redis (9 granian workers) answers 405 on `/_reflex/cookies/sync`
- `VENV=alpha2-ent APP_DIR=entauth APP_BP=8341 $W/scripts/start_app.sh prod $W/logs/p.log; $W/scripts/wait_ready.sh http://localhost:8341/ http://localhost:8341 600`
- `for i in $(seq 18); do curl -s --noproxy '*' -o /dev/null -w '%{http_code} ' -X POST http://localhost:8341/_reflex/cookies/sync -H 'Content-Type: application/json' -d '{}'; done`
  → mostly `405` (expected `400 No client token in request` from every worker).
- `$PY prod_sync_probe.py http://localhost:8341 a2 4` → login shows Alice but 3/4 attempts sync=405 and
  no `_oidc_*` cookies are stored (new tabs logged out, cross-tab sync impossible). 0.9.12 identical.
- Cause: `HTTPCookie.ensure_handlers_registered()` adds the route lazily per process on first `HTTPCookie.sync()`.

### I-3 (MEDIUM, NOT a regression): background tasks on protected states never update the page live
- Log in, open /list, click "fill": `$PY bglive_probe.py http://localhost:3340 a2 direct,loaded`.
  `direct`: progress stays 0, `item_count` shows its `-1` placeholder, items appear only after reload;
  websocket deltas carry `{"items": [], "item_count": -1, "progress": 0}`. 0.9.12: same (and loses the list).
  `loaded` (handler that calls `await self.get_state(AuthUserState)` inside every `async with self`) → live.

### I-4 (MEDIUM, NOT a regression): IdP signing-key rotation breaks every new login until the app restarts
- With the app running and one successful login done (JWKS fetched), restart the IdP:
  `$W/scripts/infra.sh restart-oidc 3600`; log in from a fresh browser → back on "Sign in"; server log:
  `InvalidKeyIdError: invalid_key_id: No key for kid` / "Tokens failed validation immediately after the
  exchange; resetting session". (`scripts/expiry_matrix.sh alpha2-ent entauth a2 restart_provider`.)

### I-5 (MEDIUM, NOT a regression): expired / revoked tokens keep authorizing protected events
- `scripts/expiry_matrix.sh alpha2-ent entauth a2 expire_norefresh revoke` (30 s token, no refresh token;
  IdP-side revocation): 40 s after expiry / right after revocation `reveal` (protected) still runs and a
  reload stays logged in; only a token refresh attempt (or the 1800 s userinfo cache) notices. 0.9.12 identical.

### I-6 (LOW, NOT a regression): MCP handler denied by its token-scope check reports success
- `$SB/envs/ent_auth2-drv/bin/python check_mcp_oauth_redis.py http://localhost:8340 http://localhost:3340 a2`
  → `mcp.scoped_write = {"is_error": false, "delta": {}}`, `scoped_writes` stays 0 (token has only
  `profile:read`; handler requires `items:write`). Same on a1 (10-06 partial).

### I-7 (LOW, NOT a regression): rxe.map layers/events gaps
- `CI=true $SB/envs/<venv>/bin/python -I $W/scripts/layers_dynimport_check.py /envs/<venv>/` prints
  `const LayersControl.BaseLayer = ClientSide(...)` (invalid JS) on 0.9.12/a1/a2; an app using those classes
  500s on every route in dev. `on_layeradd` never fires (`$PY layeradd_debug.py http://localhost:3344` with mapsapp).
