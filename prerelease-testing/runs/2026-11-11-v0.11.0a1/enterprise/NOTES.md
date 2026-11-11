# enterprise cluster — reflex-enterprise 0.9.11 (PyPI) on reflex 0.11.0a1

## Status / resume here
- DONE: step 1 static scan + import sweep; ENT-29 (entv + aggrid_min prod on new-ent).
- RUNNING/NEXT: upstream demos dnd/flow/mantine/map prod (seq_grid part 2) on new-ent; then xcut app (CORS, lifespan,
  awaited protected handler, REST/WS parity, Redis); auth (entauth + mock IdP); ag_grid/tickets/highcharts demos; prev-ent baselines.
- Venvs: `$SB/envs/new-ent` (reflex 0.11.0a1 + rxe 0.9.11[mcp], redis 8.2.0b1), `$SB/envs/prev-ent` (reflex 0.10.1 + rxe 0.9.11, redis 7.4.1).
  Both: mcp 1.30.0, oidc-provider-mock 0.4.8, starlette 1.10.0, granian 2.8.7, asgiproxy+aiohttp+PyYAML present, no fastapi, no pytest.
- Ports: fe 3380-3399, be 8380-8399; Redis 8399, mock IdP 8398, account stub 8397 (127.0.0.1).
- `SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad`; work dir `$SB/apps/enterprise/`.
- Upstream rxe source (tag v0.9.11 = b9ec0a9) became available read-only at /home/user/reflex-enterprise mid-run (demos/ + tests/).
- A real (no-permission) REFLEX_ACCESS_TOKEN became available mid-run at `$SB/secrets/reflex_access_token` (never written
  anywhere under the repo). Which runs used it vs the account stub is recorded per run below ("acct=stub" / "acct=token").

## How the fixtures are run here (ports remapped)
The checked-in fixtures (`prerelease-testing/fixtures/enterprise`) hard-code the 3600-3639/8600-8639 area. They are copied
with a port remap into `$SB/apps/enterprise/fx` by `scripts/remap_fixtures.py` (grid 36NN->33(80+NN), 86NN->83(80+NN);
auth 3620/22/23/24->3390/92/93/94, 8620..8626->8390..8396, Redis 8629->8399, IdP 8638->8398, stub 8639->8397; stop
scripts' kill ranges narrowed to 3390-3399 / 8390-8396). Env: `scripts/env.sh` (WORK=$SB/apps/enterprise/fxwork,
F=$SB/apps/enterprise/fx, ENT_REPO=/home/user/reflex-enterprise).
```
cd $SB && $SB/envs/driver/bin/python -I <DEST>/scripts/remap_fixtures.py /home/user/reflex/prerelease-testing/fixtures/enterprise $SB/apps/enterprise/fx
. <DEST>/scripts/env.sh; cd $SB
$F/grid/bin/fetch_demos.sh                       # copies upstream demos from /home/user/reflex-enterprise into $WORK/grid/demos
$F/grid/bin/seq_grid.sh new-ent new 1            # entv + aggrid_min prod (acct=stub)
$F/grid/bin/seq_grid.sh new-ent new 2            # dnd flow mantine map prod (acct=stub)
```

## Step 1 — static scan of the installed rxe 0.9.11 (new-ent site-packages/reflex_enterprise)
Raw greps kept out of the repo (they quote rxe source): `$SB/apps/enterprise/scan/grep{1,2}.txt`; import sweep: `scripts/import_all.py` -> `scan/import_*.txt`.
- Import sweep (`python -I -W default`, neutral cwd): 112/113 submodules import on BOTH venvs, 0 warnings, 0 output.
  Only `reflex_enterprise.testing.plugin` fails (`No module named 'pytest'`, the optional pytest plugin) on both: benign.
- No use of: `supervise_output` / `reflex_base.utils.log` supervisor names (#7650), `AdminDash`/`admin_dash` (#7739),
  `alembic_autogenerate`/`get_migration_history`/`format_revision`/`_alembic_` (#7742), `rx._x.client_state` /
  `ClientStateVar` / `.set_value` (#6936; the `client_state` hits are OAuth `state` params in mcp_auth), `BackendVarFormatError`,
  redis lock internals (`_lock` hits are rxe's own asyncio/threading locks), `DECORATED_PAGES`.
- `App.__call__` / Starlette (#7624): rxe never calls `app()` and never inspects its result. `proxy.py` (dev
  `use_single_port`) registers `proxy_middleware(app)` as a lifespan task and looks for a Starlette in `app` — but reflex
  passes `app=<rx.App>` to a parameter named `app` on both 0.10.1 and 0.11 (lifespan mixin `partial(task, app=self)`),
  so `_get_base_starlette_app` sees a non-Starlette on both -> runtime check below.
  MCP registers `_mcp_session_manager_lifespan` and (Redis) `_verify_redis_version_lifespan` with
  `register_lifespan_task`; its code guards against double registration on repeated `__call__`.
- `deploy_url` (#7641): read in `plugins/mcp.py` (OAuth issuer/resource origin, "deploy_url/api_url is set" error) and
  `plugins/event_handler_api.py` (server URL in openapi). Both use `config.deploy_url or ...` so None is tolerated statically.
  The only CORS code in rxe is a `Access-Control-Allow-Origin: *` on MCP `/register`; everything else relies on reflex's CORS.
- `Middleware.preprocess` (#7782): rxe ships `AuthMiddleware(Middleware)` (installed by AuthPlugin.post_compile via
  `app.add_middleware`) -> runtime check of awaited protected handlers below.
- `@rx.event` (#7673): 30+ `@rx.event` on rx.State subclasses (oidc/state.py, wrapper.py, page_guard.py, consent_state.py,
  routes.py, user_state.py); `rxe.event` calls `rx.event(**kw)(target)`; no `@rx.event` on non-state classes /
  staticmethods / module functions found. dnd/map/mantine `staticmethod(X.create)` are component namespaces (not events).
- Refs (#7694): AG Grid API uses `refs['<ref>']?.current?.api`, map uses `refs['<ref>']` and `MapLazyComponents.jsx`
  imports `refs` from `$/utils/state` and writes `refs[mapRef] = map`. 0.11 still exports `refs` and registers element
  refs via `useRegisteredRef(name)` under the same `ref_<id>` names -> runtime checked through grid/map API calls.
- `dynamic.bundled_libraries` (ENT-01): rxe `vars.py` prefers `RegistrationContext.ensure_context().bundled_libraries`, falls back to `dynamic.bundled_libraries`.

## ENT-29 / N-025 — AG Grid with state-valued column_defs, prod prerendered (new-ent, acct=stub)
- `aggrid_min` prod: **4/4 PASS** (load 1 + reload: state and literal grids show `Make, Price`). Only console error: favicon 404.
- `entv` prod s1-s13: every scenario 2h/6c (state + literal), s8 memo 2h/6c x2, s11 detail `Count, Value` x2, s12 3 badges,
  s13 dynamic route 2h/6c — identical to the 0.10.0 record. 0 page errors, 0 server tracebacks; boot = 1 `hydrate_and_load` in
  the socket.io connect auth. -> ENT-29 still fixed on 0.11.0a1.
- Server log noise: `Implicit Radix Themes enablement` deprecation (reflex_components_radix, the fixture app uses Radix
  without the plugin) and the fixture's own `disable_plugins` string deprecation — both app-side, not rxe.

## ENT-01 / ENT-02 / CLI-03 (`scripts/ent01_02.py`, both venvs, acct n/a)
`dynamic.bundled_libraries` (list, 5 entries), `from reflex.page import DECORATED_PAGES`, `get_config(reload=True)` all
work and print their `console.deprecate` text (deprecated 0.9.9, removal 1.0) on BOTH venvs; rxe `get_bundled_libraries()`
uses the RegistrationContext path (no warning). Identical to 0.10.1 -> still fixed. Output: `scan/ent01_*.txt`.
Run: `cd $SB/apps/enterprise/scan/neutral/cfg && EXPECT_VENV=$SB/envs/new-ent CI=true $SB/envs/new-ent/bin/python -I <DEST>/scripts/ent01_02.py`

## Upstream demos (fetch_demos.sh from /home/user/reflex-enterprise @ v0.9.11), prod, new-ent, acct=stub
| demo | result | notes |
|---|---|---|
| dnd | **27/27** | 0 console/page errors, 0 tracebacks |
| flow | **21/22** | only miss = the fixture's known `index lists 6 flow demos` driver expectation (index now also lists "Built with Reflex"); N-026/ENT-31 reload check passed this run (it is a race) |
| mantine | **23/23** | **0 page errors** — the 0.10.0 record had 1 (N-028 `Cannot read properties of null (reading 'name')`); not seen here |
| map | **4/4** | 54 OSM tile requests blocked by the sandbox proxy (benign) |

## xcut — own cross-cutting app (`src/xcut`, `scripts/xc.sh`, `scripts/xcut_drv.py`, `scripts/cors_probe.py`)
AuthPlugin (mock IdP `oidc-provider-mock` on :8398) + EventHandlerAPIPlugin + MCPPlugin; public `Pub` state, protected
`Vault` state; optional Starlette `api_transformer` with its own lifespan; user `register_lifespan_task`; Redis on :8399.
```
S=<DEST>/scripts; $S/xc.sh redis; $S/xc.sh idp
REDIS=1 $S/xc.sh start new-ent dev new_dev_redis                       # dev 3380/8380
ACCT=token REDIS=1 $S/xc.sh start new-ent prod <label> GRANIAN_WORKERS=2 [XC_DEPLOY_URL=http://localhost:8380] ["XC_CORS=*"] [XC_MCP=0] [XC_AUTH=0] [XC_TRANSFORMER=starlette]
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python -I $S/xcut_drv.py <fe> http://localhost:8380 <label> $SB/apps/enterprise/logs/xc_<label>.run.jsonl
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python -I $S/cors_probe.py http://localhost:8380 <label>   # foreign page on :3399
$S/xc.sh stop; $S/xc.sh idp-stop; $S/xc.sh redis-stop
```
(xc.sh / the drivers hard-code `SB`; the src copy is `$SB/apps/enterprise/src/xcut` = `<DEST>/src/xcut`.)

| run | venv | mode | acct | result |
|---|---|---|---|---|
| new_dev_redis | new-ent | dev+Redis | — | **22/22** |
| prev_prod_default | prev-ent | prod, 2 workers, Redis, deploy_url unset | token | starts; 16/22 — the 6 misses are the awaited-handler checks (`await EventSpec` is new in 0.11: `TypeError: object EventSpec can't be used in 'await' expression`, expected on 0.10.1) |
| new_prod_default | new-ent | same as above | token | **every granian worker dies at startup**: `ConfigError: MCP OAuth needs the app's public origin ... neither MCPPlugin(issuer_url=...) nor the config's deploy_url/api_url is set` -> ISSUE 1 |
| new_prod_noauth | new-ent | prod, `XC_AUTH=0` (MCPPlugin without AuthPlugin) | token | same crash -> ISSUE 1 affects any MCPPlugin app |
| new_prod_deploy | new-ent | prod, deploy_url=http://localhost:8380 | token | **22/22** |
| new_prod_nomcp | new-ent | prod, `XC_MCP=0`, deploy_url unset, Starlette transformer | token | **22/22** (AuthPlugin + REST work with deploy_url None) |
| new_prod_corsstar | new-ent | prod, deploy_url set + `cors_allowed_origins=["*"]` | token | CORS probe only |

Per-check observations (new-ent unless stated):
- **Awaited protected handler (#7782)**: anonymous `await Vault.secret_action()` from a public handler returns `None`, the
  protected body never runs (run log has 0 `secret_action_RAN`), and rxe's AuthMiddleware block sends the browser to
  `/login?redirect_to=%2F` (same as a direct protected click). Same from a background task (outside the lock), over REST
  (`/_reflex/event/<pub>/call_protected`), and after logout. Signed in as alice: returns `'secret-value-for-alice'` and runs
  exactly once. REST direct call of the protected handler from an anonymous token: HTTP 200 with an empty body and no run
  (pre-existing rxe style, cf. ENT-15).
- **REST/WS parity + redaction (ENT-16/R101-07)**: the same handler sees `client_ip=127.0.0.1` over the websocket and over
  REST with a spoofed `X-Forwarded-For: 203.0.113.9` (default `trusted_proxy_hops=0`), `client_token` length 36 on both;
  REST `session_id` is empty (no socket). REST response bodies carry `rx_router_session` with `client_token: ""` and
  `session_id: ""` (redacted), never the bearer token or the browser token; DOM has no client token. Same on prev-ent.
- **Redis (#7534)**: 5 rapid websocket clicks of a read-sleep-write handler -> n=5; 5 concurrent REST calls on one token ->
  n=5 in ~1.1 s (serialized, no stall); background task 10/10; 2 granian workers. No lock warnings, clean shutdown. Same on prev-ent.
- `@rxe.event(auth=False)` stacked over `@rx.event`: works, no deprecation printed (dev and prod).
- **Lifespan (#7624)**: user `register_lifespan_task` task starts/stops exactly once per worker (dev: 1 worker; prod: 2 workers ->
  2 starts / 2 stops), rxe's `_mcp_session_manager_lifespan` and `_verify_redis_version_lifespan` start once per worker.
  Starlette `api_transformer` with its own lifespan: on new it runs once per worker (after the Reflex tasks, stops before
  them) and its yielded state reaches `request.state` (`/xc/hello` -> `"state": "from-transformer"`); on prev it never runs
  unless registered (state `null`) — the intended #7624 change. Registering the same lifespan with `register_lifespan_task`
  too: new runs it twice and logs the documented "runs twice ... Remove the register_lifespan_task call" warning.
  Shutdown clean (granian "see ya", Reflex app stopped) on every run.
- **CORS (#7641)** (`out/cors_*.json`; foreign page http://localhost:3399, endpoints /ping, /_reflex/auth/token,
  /_reflex/event, /_reflex/retrieve_state, /_reflex/mcp/, /.well-known/oauth-authorization-server, /_reflex/cookies/sync):
  - prev-ent prod, deploy_url unset: every endpoint reflects the foreign origin (ACAO = origin, credentials true); browser
    cross-origin fetches succeed (old `*` default).
  - new-ent prod, deploy_url unset (no MCP): no ACAO, preflights 405; browser cross-origin fetches all blocked; same-origin fine.
  - new-ent prod, deploy_url=http://localhost:8380: preflights 400, no ACAO for the foreign origin, blocked; MCP's
    `/.well-known/oauth-authorization-server` still sends `ACAO: *` (MCP SDK) on the GET.
  - new-ent prod, deploy_url + `cors_allowed_origins=["*"]`: identical to prev default (REST, token, MCP all reachable cross-origin).
  - The OIDC login, callback and cookie handling are all same-origin in prod single-port, so the new default does not break
    them (login 22/22 above). Socket.io polling cross-origin answers with a duplicated `ACAO` header on prev and on new
    (`http://localhost:3399, http://localhost:3399`) -> context only, reflex-side, not new.
  - `/_reflex/cookies/sync` answers **405** in prod (2 workers) on prev AND new, so no OIDC token cookies are set in prod
    (cookies after login `[]`; dev sets 4 `_oidc_generic_*_partitioned` cookies) = known ENT-07 / rxe#262, unchanged.
- **Single-port dev proxy** (`rxe.Config(use_single_port=True)`): "Unable to find the base Starlette app. Proxying will not
  be enabled." and backend `/` 404 on new AND prev (rxe passes the reflex App to `_get_base_starlette_app`; pre-existing) -> ISSUE 3.
- openapi.yaml `servers`: present (`http://localhost:8380`) when deploy_url is set; **absent** in prod with deploy_url unset on
  new (prev derives deploy_url from the port) -> part of ISSUE 1 (same `resolve_server_url` root cause), low.
- Server log noise from rxe code on new: none (no deprecations printed from reflex_enterprise). App-side: "Page index is being
  redefined with the same component" warnings in prod on both venvs (rxe's `rxe.page` + App re-registration, pre-existing).

## Auth fixtures (OIDC, mock IdP, dev + Redis), new-ent
`ENT_DRV=enterprise-entdrv $F/auth/bin/seq_ent_auth.sh new-ent new 12` (log `logs/seq_ent_auth_new_12.txt` in $SB/apps/enterprise):
- part 1 (vauth N-032/ENT-30 verifier): stale P1/P2/P3/P4 **3/3 each**, away **3/3**, xtab **3/3, 0 accepted-after-logout**
  (race 0/3, healed), hunt loads = 1 `hydrate_and_load` per boot, relogin ok **2/2**; 0 tracebacks. = 0.10.0 record.
- part 2 (entauth explorer): `drive_auth_redis` cycle/pubnav/twotab/xtab **ALL_PASSED**, `xtab_probe` **TAB1_LOGGED_OUT 5/5**,
  `stale_hash_probe` **CORRECTED 3/3 x3**, hydration SUMMARY verbatim the 0.10.0 line; 0 tracebacks / 0 TypeError.
  Console noise only the mock-IdP pico.css tunnel error + cookie-sync keepalive aborts (known benign).
`enterprise-entdrv` venv = reflex 0.11.0a1 + reflex-enterprise[mcp] 0.9.11 + playwright 1.63.0 + httpx + pytest (PyPI).
