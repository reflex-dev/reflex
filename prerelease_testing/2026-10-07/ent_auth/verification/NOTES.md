# Verification of ent_auth claims A-1 (cross-tab logout) and A-2 (prod multi-worker cookie sync 405)

Verifier: independent adversarial pass, 2026-10-07 ~12:40-14:10 UTC. My own minimal app + Playwright
driver, written BEFORE reading the explorer's probes (compared afterwards, see the end).
Packages: PyPI-only venvs plus the offline wheel `reflex_enterprise-0.9.7a4-py3-none-any.whl` by file path.

## Verdicts (short)

| claim | verdict | regression? |
|---|---|---|
| A-1 logout in one tab leaves other tabs signed in | **CONFIRMED** (plus a deterministic, race-free form that is worse than claimed) | **yes**, since 0.10.0a1 (#7064); 0.9.12 + same wheel correct |
| A-1 claimed mechanism (single `hydrate_and_load` boot bypasses `OIDCAuthState.get_delta` hash reconciliation) | **CONFIRMED** (frame-level and source-level); nuance: the cross-tab race itself is pre-existing, 0.9.12 only heals it at the next boot | — |
| A-2 prod multi-worker `/_reflex/cookies/sync` 405 → token cookies not stored | **CONFIRMED, NARROWED** (rate depends on worker warm-up: 5/6 failing on a freshly started server, ~1/4 after ~25 logins) plus an unreported side effect (cross-tab request storm) | **no** (0.9.12 identical) |

## Environment

```
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
W=$SB/apps/verify_ent_auth_0           # work dir (this directory's app/, drivers/, bin/ are copies of it)
```
Venvs (Python 3.12, checked with `uv --no-config pip freeze`):
- `$SB/envs/alpha2-ent` (shared, read-only): reflex 0.10.0a2 + reflex-base 0.10.0a2 + 0.10 train, enterprise wheel 0.9.7a4 (file://), oidc-provider-mock 0.4.8, greenlet 3.5.6, granian 2.8.4, starlette 1.7.0.
- `$SB/envs/ent_auth2-a1w` (created by the explorer, PyPI + wheel only): reflex 0.10.0a1 + wheel 0.9.7a4 + greenlet.
- `$SB/envs/ent_auth2-s912w` (created by the explorer, PyPI + wheel only): reflex 0.9.12 + wheel 0.9.7a4 + greenlet.
- `$SB/envs/driver`: Playwright 1.63, Chromium `/opt/pw-browsers/chromium`.
(No new venv was needed. Any new `reflex[db]` venv needs `greenlet` — N-001.)

Ports (verifier range): dev frontend 3720 / backend 8720; prod single port 8721; redis 8739; mock IdP 8738.
Every server run: `CI=true REFLEX_TELEMETRY_ENABLED=false AUTHLIB_INSECURE_TRANSPORT=1
OIDC_ISSUER_URI=http://localhost:8738 OIDC_CLIENT_ID=vauth-client OIDC_CLIENT_SECRET=vauth-secret
REFLEX_REDIS_URL=redis://localhost:8739` (see `bin/start_app.sh`). Drivers run with
`NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1` on the client side only.

## App (`app/`) and drivers (`drivers/`)

- `app/vauth/vauth.py` (+ `app/rxconfig.py`): `rxe.Config(plugins=[AuthPlugin()])` (secure by default,
  default `GenericOIDCAuthState`), `rxe.App`. Pages: `/` public (`auth=False`, shows `AuthUserState.sub`),
  `/vault` protected by the plugin default (shows `AuthUserState.sub`, protected `Vault.clicks`/`entries`,
  protected event `add_entry` that records the identity the server attributes to it via
  `AuthUserState.current()`, and a logout button = `AuthUserState.logout`), `/pid` public.
  `VAUTH_PID_HEADER=1` wraps the backend ASGI app (`api_transformer`) to add an `x-worker-pid` response
  header — used only for the A-2 per-worker tables.
- `coregd_app/`: core-only (no enterprise) app whose state overrides `get_delta` (with the same private
  `rx.state._override_base_method` decorator the wheel uses) and prints `GET_DELTA_SAW theme=...` for every
  LocalStorage value that passes through it.
- `drivers/vdrv.py` modes (all record websocket frames (socket.io connect + event packets, parsed), console,
  page errors, failed requests, `/_reflex/cookies/sync` statuses+pid, and — via an init script + exposed
  binding — every localStorage write of the token hash and every `storage` event, per tab):
  - `xtab <base> <label> N` — manual two-tab flow: tab1 logs in as alice on /vault; tab2 (same context)
    opens /vault (signed in via cookies), clicks logout, "End session" at the IdP, lands on `/`; wait 8 s;
    tab1 clicks the protected `add`; reload tab1; open a fresh tab3 on /vault.
  - `stale <base> <label> N` — deterministic probes: P1 anonymous tab boots with a bogus hash in
    localStorage (expect corrected to ""); P2 logged-in tab boots with a bogus hash (expect real hash
    re-asserted); P3 logged-in tab away on about:blank while a helper tab clears the cookies and writes
    hash "" (the end state of a completed logout), tab returns to /vault (expect /login); P4 control: same
    end state delivered live by a storage event (expect logged out).
  - `away <base> <label> N` — realistic race-free form: tab1 (alice, /vault) navigates to another origin;
    user logs out normally in tab2 (real UI + IdP end_session); tab1 presses Back.
  - `logins <base> <label> N` — N full logins in fresh contexts; token cookies present? sync status/pid;
    a second tab on /vault signed in?
  - `logoutcookies`, `storm` — A-2 side checks (see below).
- `drivers/timeline.py <json> <rep> [logkey]` — compact per-tab timeline (SEND/RECV/LS_SET/STORAGE_EVENT/COOKIE_SYNC/NAV).
- `drivers/race.py <xtab json>...` — per repetition: did the race happen (tab1 re-wrote the old hash after
  tab2's logout) and who wrote "" when.
- `drivers/noise.py <json>` — console/network noise summary. `drivers/coregd_drv.py <base>`.
- `bin/infra.sh start|stop`, `bin/start_app.sh <venv> <appdir> <dev|prod> <log>`, `bin/stop_app.sh`,
  `bin/wait_ready.sh`, `bin/post_sync.sh <base> <N> <out>` (N POSTs to `/_reflex/cookies/sync`, status per pid).

## Rerun commands

```sh
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/verify_ent_auth_0
mkdir -p $W/logs $W/shots; cp -r <this dir>/bin <this dir>/drivers $W/
for v in a2 a1 s912; do mkdir -p $W/vauth_$v; cp -r <this dir>/app/* $W/vauth_$v/; done
$W/bin/infra.sh start                                   # redis :8739 + oidc-provider-mock :8738
# A-1 (repeat per build: alpha2-ent/vauth_a2, ent_auth2-a1w/vauth_a1, ent_auth2-s912w/vauth_s912)
redis-cli -p 8739 flushall
$W/bin/start_app.sh alpha2-ent vauth_a2 dev $W/logs/a2-dev-redis.server.log
$W/bin/wait_ready.sh http://localhost:3720/ http://localhost:8720 400
cd $W/drivers; export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1; PY=$SB/envs/driver/bin/python
$PY vdrv.py xtab  http://localhost:3720 a2-dev-redis 6 ; $PY race.py ../logs/a2-dev-redis-xtab.json
$PY vdrv.py stale http://localhost:3720 a2-dev-redis 3
$PY vdrv.py away  http://localhost:3720 a2-dev-redis 3
$W/bin/stop_app.sh
# prod, 1 worker (A-1 in prod without the A-2 confound)
GRANIAN_WORKERS=1 $W/bin/start_app.sh alpha2-ent vauth_a2 prod $W/logs/a2-prod-redis-1w.server.log
$W/bin/wait_ready.sh http://localhost:8721/ http://localhost:8721 400; $PY vdrv.py xtab http://localhost:8721 a2-prod-redis-1w 6
# A-2: default workers (9 on this 4-CPU box), fresh server
VAUTH_PID_HEADER=1 $W/bin/start_app.sh alpha2-ent vauth_a2 prod $W/logs/a2-prod-redis-9w.server.log
$W/bin/wait_ready.sh http://localhost:8721/ http://localhost:8721 400; sleep 20
$W/bin/post_sync.sh http://localhost:8721 27 $W/logs/a2-prod-9w-post-fresh.txt
$PY vdrv.py logins http://localhost:8721 a2-prod-redis-9w 6
$W/bin/post_sync.sh http://localhost:8721 27 $W/logs/a2-prod-9w-post-after-logins.txt
$PY vdrv.py storm http://localhost:8721 a2-prod-redis-9w-b 3
# control: GRANIAN_WORKERS=1 VAUTH_PID_HEADER=1 ... same commands; baseline: ent_auth2-s912w vauth_s912
$W/bin/stop_app.sh; $W/bin/infra.sh stop
```

## A-1 results

### Two-tab manual flow (`xtab`), "tab1 logged out" = protected `add` refused AND reload lands on /login

| build | tab1 logged out | race happened (tab1 re-wrote the old hash after tab2's logout) | outcome when the race happened |
|---|---|---|---|
| 0.10.0a2 + wheel, Redis, dev | **1/6** | 5/6 | stayed signed in 5/5 |
| 0.10.0a2 + wheel, Redis, prod (`GRANIAN_WORKERS=1`) | **3/6** | 3/6 | stayed signed in 3/3 |
| 0.10.0a2 + wheel, memory manager, dev | 4/4 | 0/4 | — |
| 0.10.0a1 + wheel, Redis, dev | **5/11** (5/6 + 0/5) | 6/11 | stayed signed in 6/6 |
| 0.9.12 + wheel, Redis, dev | **6/6** | **6/6** | healed 6/6 (tab2's boot `reconcile_tokens_after_sync` writes "", tab1 resets) |

In every "stayed" repetition: browser has NO `_oidc_*` cookies, the IdP session was ended, tab1's
protected `add` ran as alice (`click1:alice`, clicks 0→1), a reload of tab1 still shows `who=alice` on
/vault (boot echoes the stale hash), a NEW tab on /vault correctly lands on /login.
Logs: `logs/{a2-dev-redis,a2-prod-redis-1w,a2-dev-memory,a1-dev-redis,a1-dev-redis-b,s912-dev-redis}-xtab.json.gz`
(`_full_log` = every frame/storage/cookie event), screenshots `shots/*-xtab-*-tab1-after-{add,reload}.png`.

Timeline of a failing a2 repetition (`timeline.py a2-dev-redis-xtab.json 0`, t=0 at the logout click):
```
+0.04 tab2 SEND logout                 +0.05 tab2 RECV hash ''  -> LS_SET ''
+0.05 tab1 STORAGE_EVENT H -> ''       +0.05 tab1 SEND update_vars_internal(hash '')   (mismatch -> sync)
+0.07 tab2 COOKIE_SYNC 200 (clears)    +0.07 tab1 COOKIE_SYNC 200  <- sent with the OLD cookies (race)
+0.07 tab1 SEND reconcile_tokens_after_sync -> tokens "present" -> RECV hash H -> LS_SET H (stale hash back)
+0.74 tab2 (back from IdP) SEND hydrate_and_load(hash H) -> RECV {is_hydrated: False, hash: H}   (echo, no reconcile)
+6.86 tab1 SEND add_entry -> RECV clicks 1      +10.06 tab1 reload: hydrate_and_load -> user_sub alice
```
On 0.9.12 the same race happens (6/6), but tab2's return boot sends `hydrate`, `update_vars_internal`
(hash H), `on_load_internal`; the `update_vars_internal` delta passes `OIDCAuthState.get_delta` →
H ≠ "" → `HTTPCookie.sync(reconcile_tokens_after_sync)` → no cookies → `reset_auth` → hash "" → tab1's
storage event → tab1 reset. The heal is visible in `race.py` as tab2/tab1 "" writes at ~+0.7-0.9 s.

Nuance (exposure window on 0.10): the stale tab is healed only when ANOTHER tab whose session hash differs
sends `update_vars_internal` (0.10 still sends it on client-side navigation and storage events), e.g. a
new tab opened on a protected page (guard redirect → client nav → reconcile): in the a2 runs tab3 at
~+15.6 s wrote "" and tab1 reset right after. Without such an action tab1 stays signed in.

### Deterministic probes (`stale`, `away`)

| probe | 0.9.12 + wheel | 0.10.0a1 + wheel | 0.10.0a2 dev Redis | 0.10.0a2 prod Redis (1 w) | 0.10.0a2 dev memory |
|---|---|---|---|---|---|
| P1 anon tab boots with bogus hash → corrected to "" | 3/3 | 0/3 | 0/3 | 0/3 | 0/2 |
| P2 signed-in tab boots with bogus hash → real hash re-asserted | 3/3 | 0/3 | 0/3 | 0/3 | 0/2 |
| P3 signed-in tab returns after cookies cleared + hash "" (no live storage event) → signed out | 3/3 | 0/3 | 0/3 | 0/3 | 0/2 |
| P4 control: same end state by live storage event → signed out | 3/3 | 3/3 | 3/3 | 3/3 | 2/2 |
| `away`: real logout in tab2 while tab1 is on another origin; tab1 presses Back → signed out | **3/3** | **0/3** | **0/3** | **0/3** | — |

The `away` result is the strongest form: NO race needed — a clean logout (cookies gone, hash "" in
localStorage) and the tab that comes back (Back button; equally a discarded/frozen tab that reloads) is
fully signed in as alice and its protected event runs (`shots/a2-dev-redis-away-0-tab1.png`:
`who=alice clicks=1 click1:alice`). Logs `logs/*-stale.json.gz`, `logs/*-away.json.gz`.

### Boot events (client → server) per version
- 0.9.12: `hydrate`, `update_vars_internal` (all client-storage vars), `on_load_internal`; then
  `reconcile_tokens_after_sync` whenever the hash mismatched.
- 0.10.0a1 / 0.10.0a2: a single `hydrate_and_load` (carried in the socket.io CONNECT packet
  `40/_event,{"event":{"name":"...hydrate_and_load","payload":{"vars":{...},"hashes":[...]}}}`); the reply
  echoes the browser's hash with `is_hydrated: False` (so the frontend does not even rewrite it); no cookie
  sync, no reconcile. Client-side navigation and storage events still send `update_vars_internal`.

### Mechanism — CONFIRMED (published sources)
- `reflex/state.py` (0.10.0a2 site-packages) `State.hydrate_and_load` lines 2338-2389:
  2365 `_reset_client_storage()`, 2367 `_apply_client_storage_vars(self, vars)`, **2368 `self._clean()`**,
  2375 `self.dict()`, 2379 `self._get_resolved_delta()` — the applied client-storage vars are no longer
  dirty when the delta is built, so no `get_delta` override sees them (0.10.0a1: same code, 2312-2363).
- 0.9.12 `reflex/state.py`: `hydrate` (2935) then `UpdateVarsInternalState.update_vars_internal` (3070)
  sets the vars dirty → normal `get_delta` path.
- Wheel `reflex_enterprise/auth/oidc/state.py` 2538-2541 `OIDCAuthState.get_delta` →
  `_handle_latest_access_token_hash_ls_in_delta` (617-676) — only acts when `latest_access_token_hash_ls`
  is in the delta.
- Core-only confirmation (`coregd_app`, `logs/coregd-{a2,s912}.server.log.gz`, `logs/coregd-*.driver.out`):
  boot with localStorage `bogus-boot`, then client-side nav with `bogus-nav`:
  0.9.12 prints `GET_DELTA_SAW theme='bogus-boot'` and `'bogus-nav'`; 0.10.0a2 prints only `'bogus-nav'`.
- PR #7064 ("one boot event ... hydrate, update_vars_internal, on_load_internal → hydrate_and_load",
  labelled non-breaking for apps) does not mention `get_delta` overrides.

### Blast radius
- Wheel `get_delta` overrides / boot hooks (grep of site-packages/reflex_enterprise):
  1. `OIDCAuthState.get_delta` (hash reconciliation) — **affected** (this issue).
  2. `auth/enforcement.py:1561-1628 install_delta_filter` wraps BOTH `get_delta` and `dict`; the `dict`
     wrapper covers `hydrate_and_load`'s snapshot, so protected-field withholding at boot is NOT bypassed.
  3. `auth/enforcement.py:1695` `AuthMiddleware.preprocess` already special-cases `{"hydrate","hydrate_and_load"}`.
  4. `auth/replay.py:128` only CALLS `pending.get_delta()`; `PendingEventState`, `redirect_to_url`,
     `app_state`, `code_verifier`, `rejected_state_digest` are read in handlers after the vars are applied.
  No wheel code references `update_vars_internal`. So in the wheel only the OIDC cross-tab hash
  reconciliation depends on boot-time client storage passing through `get_delta`.
- Core: any app state that overrides `get_delta` (private `rx.state._override_base_method`; a plain
  override is rejected with `EventHandlerShadowsBuiltInStateMethodError` on both versions) to react to
  client-storage values no longer sees them at boot/reload/reconnect. Private API → narrow, but it is
  exactly the pattern the enterprise package uses.

### Judgement
Security-relevant regression in enterprise OIDC logout on 0.10 (a1 and a2): after an explicit logout,
other tabs of the same browser keep full authenticated access (protected events + reload), with a
race-free deterministic path (Back / returning tab: 0/3 vs 3/3) and a frequent racy path (0.10 failed in
14 of 27 two-tab repetitions overall (a2 dev 5/6, a2 prod 3/6, a2 memory 0/4, a1 6/11), 0.9.12 0/6). Limited to the same browser that logged out, new tabs
are anonymous, IdP session ended → HIGH. Recommend treating it as a **release blocker for 0.10.0 final**
for the reflex + reflex-enterprise pair: fix either in core (let client-storage values applied by
`hydrate_and_load` reach `get_delta` overrides, or keep an explicit hook) or in enterprise (do the hash
check from a `hydrate_and_load`-aware hook, e.g. next to `AuthMiddleware.preprocess`).

## A-2 results

`reflex run --env prod` with `REFLEX_REDIS_URL` spawned 9 granian workers (`(cpu*2)+1`, log "Spawning
worker-1..9"). `x-worker-pid` from the verifier app's ASGI wrapper.

| run | POST /_reflex/cookies/sync (no client token; correct answer is 400) | full logins with token cookies stored |
|---|---|---|
| 0.10.0a2, 9 workers, fresh | 27/27 **405** over 8 distinct pids | **1/6** (each failing login: its one sync POST got 405) |
| same server after those 6 logins | 19×400 / 8×405 — 7 pids answer 400, 2 pids still 405 | — |
| same server after ~20 more logins | 23×400 / 4×405 (same 2 pids) | 3/4 |
| 0.10.0a2, `GRANIAN_WORKERS=1`, fresh | 18/18 405 (no event has built `HTTPCookie.sync()` yet) | **5/5**; afterwards 18/18 400 |
| 0.9.12, 9 workers, fresh | 27/27 405 over 9 pids | **1/6**; afterwards 22×400 / 5×405 |

Tables: `logs/*-post-*.txt`; logins: `logs/{a2-prod-redis-9w,a2-prod-redis-9w-warm,a2-prod-redis-1w,s912-prod-redis-9w}-logins.json.gz`.
In every failing login the tab itself showed alice (session holds the tokens), but a second tab landed
on /login. Cause (wheel `reflex_enterprise/auth/cookie.py:374-385`): `ensure_handlers_registered()` inserts
the POST route into `app._api.routes` of the CURRENT process only, and is only called from
`HTTPCookie.sync()` (line 440) — i.e. in a worker that has processed an event building a sync. The POST
lands on any worker; a cold one falls through to the prod static mount → 405.

Narrowing: the failure rate is "fraction of workers that have not yet processed such an event", so it is
~100% right after every start/deploy/worker respawn and decays with websocket traffic; workers that
receive no websocket traffic stay cold indefinitely (2/9 here after ~30 logins). "~3 of 4 logins" holds
for a fresh / lightly used server only.

Not observed: a logout whose cookie-CLEARING sync 405s (would leave token cookies behind): 0/5
(`logoutcookies`; the logout sync reused a warm worker each time).

Additional side effect (pre-existing, not in the explorer's report): after a login whose sync got 405,
opening a second tab starts a cross-tab ping-pong — tab A (has tokens) re-asserts hash H, tab B (none)
resets to "", each through `update_vars_internal` → `reconcile_tokens_after_sync` → cookie sync (405).
`storm` mode, a2 9 workers: 1 of 3 repetitions sustained ~115 cookie-sync POSTs/s + ~155 websocket
events/s for the whole 40 s window (`a2-prod-redis-9w-b-storm.json.gz`: 500-624 POSTs per 5 s), the
other 2 ended within 5 s by logging the FIRST tab out. The `logins` runs show the same on 0.9.12
(3 of 5 failed-sync logins: 336-409 POSTs per tab over the 10.8 s window). Console shows one
"405 (Method Not Allowed)" error per POST (1400 in a2's 6 logins, 1693 in 0.9.12's).

Severity: HIGH is fair — every multi-worker (= default with Redis) prod deployment with enterprise auth
after each restart, new tabs logged out, refreshed tokens never persisted, and a possible request storm —
but it is NOT a 0.10 regression, so it should not block reflex 0.10.0 by itself; it needs an enterprise
fix (register the route at app construction / `AuthPlugin.post_compile` in every worker).

## Noise seen (all versions, benign)
`/_reflex/cookies/sync` `net::ERR_ABORTED` for keepalive POSTs cut by navigation (a2 dev xtab 40, 0.9.12 42,
a1 27); mock IdP `pico.min.css` ERR_TUNNEL_CONNECTION_FAILED (sandbox proxy); one `/favicon.ico` 404.
Server logs: no tracebacks in any run; dev logs show the deprecation for string `disable_plugins`
(my rxconfig) and the implicit Radix Themes deprecation.

## Comparison with the explorer (done after my runs)
The explorer's `xtab_probe.py` / `stale_hash_probe.py` / `prod_sync_probe.py` test the same flows on a
bigger app (`/list`, `/dashboard`). Numbers agree: a2 dev 3/7 (mine 1/6), a2 prod 3/5 (mine 3/6),
a1 2/6 (mine 5/11), 0.9.12 6/6 (mine 6/6); boot-correction 0/N vs 2/2 (mine 0/3 vs 3/3); prod 405 /
"3 of 4" (mine 5/6 on a fresh server). The explorer's written repro (NOTES "I-1"/"I-2") was sufficient
to reconstruct the scenarios independently. New here: the race-free `away`/P3 form, the race-vs-outcome
correlation (the race is pre-existing; 0.9.12 heals it at the next boot), the core-only `get_delta`
demonstration, the per-worker 405 table with pids, the warm-up decay and the cross-tab request storm.
