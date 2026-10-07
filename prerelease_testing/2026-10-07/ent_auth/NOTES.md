# Cluster `ent_auth` — enterprise OIDC / MCP / maps on reflex 0.10.0a2 + offline reflex-enterprise 0.9.7a4

Status: IN PROGRESS (this file is written incrementally; the final section "Results" is authoritative).

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
