# enterprise cluster — reflex-enterprise 0.9.11 (PyPI) on reflex 0.11.0a1

## Status / resume here
- DONE: step 1 static scan + import sweep; ENT-29 (entv + aggrid_min prod on new-ent).
- DONE also: demos dnd/flow/mantine/map prod, xcut (CORS/lifespan/await/parity/Redis), auth parts 1-3 new + part 3 prev, ISSUE 1-3.
- COMPLETE (2026-11-11 ~01:55 UTC). Report: ../reports/enterprise.md. All servers/Redis/IdP/stub stopped.
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
- part 3 (a4 matrix, dev, memory; `seq_ent_auth.sh <venv> <L> 3`): new-ent **36/36** (auth-full 22/22, reload 3/3,
  auth-min default 4/4, iframe 3/3, extra scopes 4/4) + anonymous MCP pass, BUT **MCP OAuth FAILS** (driver times out
  waiting for `/login` after opening the authorization URL). prev-ent baseline (same command, label prev): 36/36 + MCP OAuth
  pass + anonymous MCP pass -> regression, ISSUE 2.

## ISSUE 1 — MCPPlugin app dies at startup under `reflex run --env prod` (deploy_url unset)
Minimal repro: `src/mcpmin` (rxe.Config(plugins=[rxe.MCPPlugin()]) + one page) and `scripts/repro_mcp_prod.sh`
(port 8381, 1 worker, REFLEX_API_URL=http://localhost:8381). Output `out/repro_mcp_prod.txt`:
| venv | acct | extra env | result |
|---|---|---|---|
| new-ent | token | — | every worker exits: `ConfigError: MCP OAuth needs the app's public origin for the RFC 8414 issuer, but neither MCPPlugin(issuer_url=...) nor the config's deploy_url/api_url is set` |
| new-ent | stub | — | same (token vs stub: no difference) |
| prev-ent | token | — | starts, serves |
| new-ent | token | REFLEX_DEPLOY_URL=http://localhost:8381 | starts, serves (workaround) |
Also hit by the xcut app with AuthPlugin+MCPPlugin and with MCPPlugin alone. Cause: reflex 0.11 prod always mounts the
compiled frontend into the backend (`REFLEX_MOUNT_FRONTEND_COMPILED_APP`), and rxe's `resolve_server_url()` then returns
`config.deploy_url`, which #7641 changed from "derived from frontend_port" to `None`. The error message even says "api_url
is set" is enough, but api_url IS set here. Same root cause: openapi.yaml loses its `servers` entry in prod. Fix belongs
to reflex-enterprise (fall back to `config.frontend_url` / `api_url` when deploy_url is None); a reflex-side mitigation
would be a breaking-change note naming downstream readers of `deploy_url`.

## ISSUE 2 — MCP OAuth consent redirect goes to the backend origin in dev (deploy_url unset)
`scripts/mcp_consent_probe.py` against the a4auth `auth_min` app in dev (frontend 3393, backend 8393), out `out/mcp_consent_*.txt`:
- new-ent: `/authorize` -> `302 Location: http://localhost:8393/agent-consent?txn=...` -> **404 Not Found** (backend origin).
- prev-ent: `302 Location: http://localhost:3393/agent-consent?txn=...` -> 200 (frontend page).
- new-ent with `REFLEX_DEPLOY_URL=http://localhost:3393`: 302 to 3393, 200; the full fixture `check_mcp_oauth.py` then passes
  ("MCP OAuth discovery, registration, browser consent, PKCE, protected event, code replay and refresh rotation passed",
  `out/mcp_oauth_new_deploy.txt`).
Cause: rxe `MCPPlugin._resolve_consent_url` uses `config.deploy_url or issuer_url`; deploy_url is None on 0.11 by default,
so the consent page is addressed on the backend. Fix in reflex-enterprise: use `config.frontend_url` (new in 0.11) when present.
Repro:
```
. <DEST>/scripts/env.sh; ENT_DRV=enterprise-entdrv $F/auth/a4auth/fetch_upstream.sh /home/user/reflex-enterprise
$F/auth/bin/infra.sh start; cd $WORK/auth/a4auth/apps/auth_min
CI=true OIDC_ISSUER_URI=http://localhost:8398 OIDC_CLIENT_ID=reflex-integration-test OIDC_CLIENT_SECRET=reflex-integration-test-secret AUTHLIB_INSECURE_TRANSPORT=1 setsid $SB/envs/new-ent/bin/reflex run --frontend-port 3393 --backend-port 8393 &
$SB/envs/new-ent/bin/python -I <DEST>/scripts/mcp_consent_probe.py http://localhost:8393
```

## ISSUE 3 (pre-existing) — `rxe.Config(use_single_port=True)` dev proxy never mounts
new-ent and prev-ent alike: "Unable to find the base Starlette app. Proxying will not be enabled." and the backend port
answers 404 for `/` (with and without an api_transformer). rxe's `proxy_middleware(app)` lifespan task receives reflex's
`App` (reflex binds a parameter named `app` to the rx.App), not a Starlette. Upstream AG Grid demo's rxconfig sets
`use_single_port=True`. Not a 0.11 regression. Repro: `XC_SINGLE=1 $S/xc.sh start <venv> dev l; curl localhost:8380/` -> 404.

## More upstream demos, prod (acct=stub via the fixture start.sh)
| demo | new | prev | notes |
|---|---|---|---|
| tickets (EventHandlerAPIPlugin) | UI **18/18**; API as before: openapi.yaml 200 (PyYAML present), malformed JSON -> 500, handler arg errors -> HTTP 200 + error body (ENT-15, known), unknown handler -> 405 from the frontend mount; REST bodies show `rx_router_session.client_token == ""` | not re-run (no failure) | 3 server tracebacks = the malformed-JSON / handler-error paths (ENT-15) |
| highcharts | **13/13** | not re-run | 5 console warnings = Highcharts accessibility module notice (known benign) |
| AG Grid demo (`enterprise-demo-new` / `-prev` venvs: reflex[db] + rxe[mcp] 0.9.11 + faker/pandas/aiosqlite) | smoke **20/20**, coldefs **7/7**, features **39/48**, model 24/29 | smoke 20/20, coldefs 7/7, features **46/47**, model 24/29 | new-only feature failures = ISSUE 4 (tree column-state save/load, aligned grids x2, state-grid `select_all_on_load`, selected-items Select All); `clipboard` + the 5 model misses are the known pre-existing ones (ENT-32, driver assumption); the 2 tracebacks are the known `met` string -> SQLite DateTime (both) |
`ag_demo.sh` also runs `reflex db migrate` first -> ISSUE 5.

## ISSUE 4 — rxe AG Grid API calls (`grid.api.*`, `AgGridAPI`, `aligned_grids`) throw `ReferenceError: refs is not defined`
Minimal repro `src/agapi` + `scripts/agapi_drv.py` (out `out/agapi.txt`): a grid with `id="grid1"`, buttons
`grid.api.select_all()` and `grid.api.getSelectedRows(callback=S.got_rows)`.
- new-ent prod: 0 rows selected, State stays -1; server log 4x `[Reflex Frontend Exception] ReferenceError: refs is not defined`.
- new-ent dev: same (4x).  prev-ent prod: PASS (3 rows selected, State 3), 0 errors.
Cause: the compiled page module uses `refs['ref_grid1']?.current?.api` (rxe `AgGridAPI._api` / `_format_props(aligned_grids)`)
without importing `refs`. On 0.10.1 every page with a ref imported `refs` from `$/utils/state`; 0.11 (#7694 element refs via
`useRegisteredRef`) imports only `useRegisteredRef` (`_index.jsx`: new `import {useRegisteredRef} from "$/utils/state"` vs
prev `import {refs} from "$/utils/state"`). `rxe.map`'s API already attaches `refs_var_data` and is unaffected; `rx.call_script`
code (OIDC refresh timer) is evaluated inside state.js where `refs` exists. Fix: reflex-enterprise should attach
`VarData(imports={"$/utils/state": ["refs"]})` to `AgGridAPIVar` and the aligned-grids var; reflex could keep exporting the
implicit import for compatibility. Severity high: every AG Grid API action silently does nothing (only a server-log line).
```
XC_SRC=$SB/apps/enterprise/src/agapi ACCT=token <DEST>/scripts/xc.sh start new-ent prod agapi_new
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python -I <DEST>/scripts/agapi_drv.py http://localhost:8380 new; <DEST>/scripts/xc.sh stop
```

## ISSUE 5 — `reflex db migrate` (and `db init` / `makemigrations`) exits 1 on the upstream AG Grid demo from a fresh checkout
`cd <copy of demos/ag_grid> && rm -f reflex.db && CI=true REFLEX_DB_URL=sqlite:///reflex.db $SB/envs/enterprise-demo-new/bin/reflex db migrate`
-> tables are created, then `ValueError: Library @radix-ui/themes is not bundled. Use ... bundle_library('@radix-ui/themes')`
(rxe `vars.py::_validate_and_extend_return_expr` while reflex serializes the initial state in `migrations.evaluate_pages()` ->
`get_compiled_app(dry_run=True)` -> `_compile_initial_state`), exit 1 (`logs/agmig_new.log`). prev-ent: exit 0 (0.10.1 `db
migrate` only imports the app). With a `.web` left by an earlier compile, new exits 0 (the skip-compile path restores the
bundled-library list from `.web`). So on 0.11 a fresh clone / CI / Docker image running `reflex db migrate` before the first
`reflex run` fails for any rxe app whose state holds an `rxe` lambda/cell-renderer that uses Radix components. Also printed on
that run (expected, #7742): "Updated env.py to load the app; the previous one is kept as alembic/env.old" (the demo ships the
stock env.py). Fix: reflex (dry-run/skip-compile evaluation should collect bundled libraries before compiling state, or not
compile initial state for `reflex db`), or rxe (defer the bundled-library check). Label both; reflex first (regression from the
new `evaluate_pages` step).

## Dev-mode runs, new-ent (`logs/seq_dev_new.txt`)
- dnd **27/27**, flow **22/22** (dev has no "Built with Reflex" index entry, so the prod-only driver miss is absent),
  mantine **23/23** (0 page errors), map **4/4** (tiles blocked) — 0 tracebacks each.
- aggrid_min dev **4/4** (ENT-29 also fine in dev).
- `seq_deeplink.sh new-ent new dev` (vauthd, Redis): A-G **3/3 each** (G = no cookie / HttpOnly token value inside
  `rx_router_headers`, ENT-16/DOC-14 browser side), 108 audit records, 0 page_load on a stale route; 0 tracebacks.
- `expiry_matrix.sh new-ent new proactive` (75 s tokens, 120 s idle): still Alice, `reveal_after_120s: allowed:revealed-alice`,
  reload stays on /dashboard, 4 OIDC cookies = 0.10.0 record (the OIDC refresh timer's `refs[...]` runs via `rx.call_script`
  inside state.js, so ISSUE 4 does not reach it).
- Dev log noise worth knowing:
  - rxe's own code prints `VarData(position=...) has been deprecated in version 0.10.1` from `components/dnd/dnd.py` (x3)
    and `components/mantine/combobox.py` on every compile. The deprecation exists on 0.10.1 too (not new) -> rxe tracker, low.
  - reflex's new dev event-loop blocking monitor (#7672) warned once on the flow demo: `Event handler
    AddNodesOnEdgeDropState.handle_connect_end is blocking the event loop (threshold: 0.200s)` with the stack ending in
    reflex's own lazy `from reflex.model import Model` inside `base_state_processor._transform_event_arg` (0.219 s on the
    first typed-payload event). Reflex-side anomaly (the monitor blames the user's handler for reflex's first-use import), low.
  - Upstream demos' own deprecations (strings in `disable_plugins`, `@rx.memo` without annotations, `ArrayVar.foreach`,
    `App(theme=...)`, implicit Radix) are demo-side.
- No rxe-originated deprecation from the 0.11 train (#7673/#7770 decorator order, stateless handlers, #6936, #7642) was
  printed anywhere; `rxe.event` stacked over `rx.event` is silent. rxe declares no set/frozenset state vars (#7642 n/a).

## Account: token vs stub
Runs with the real token (`ACCT=token`, `$SB/secrets/reflex_access_token`, never written to the repo): all xcut prod runs,
agapi prod runs, `repro_mcp_prod.sh ... token`. Fixture-driven prod runs (seq_grid, demo.sh, ag_demo.sh) used the account stub.
The only side-by-side (`repro_mcp_prod.sh new-ent token` vs `stub`) behaved identically; no behaviour difference seen.
Logs copied here were grepped for `rfx_` (none) and anonymous REST `access_token` values were redacted.

## Not covered
- prod OIDC suites of the fixtures (`seq_n032_prod.sh`, `prod_suite.sh`, `seq_n033.sh`): xcut covered prod login/logout with
  2 workers + Redis instead; `prod_suite.sh` uses entauth (MCPPlugin), which cannot start on 0.11 prod without deploy_url (ISSUE 1).
- vauthx/vea storage suites (ENT-39/ENT-40), azure, highcharts/tickets dev, flow N-026 A/B, `reflex export` of an rxe app.

## VERIFICATION
Independent adversarial verifier `verify_ent`, 2026-11-11. Fresh PyPI venvs, built with cwd=$SB and `--no-config`:
`$SB/envs/vent-new` (reflex[db]==0.11.0a1 `--prerelease=allow`, reflex-enterprise[mcp]==0.9.11, redis 8.2.0b1) and
`$SB/envs/vent-prev` (reflex[db]==0.10.1 without `--prerelease`, every `reflex*` sibling constrained to `$SB/envs/prev`'s freeze,
reflex-enterprise[mcp]==0.9.11, redis 7.4.1). Both also have faker 36.2.2, pandas 2.2.3, aiosqlite and greenlet for the AG Grid demo.
`$SB/envs/vent-idp` holds oidc-provider-mock 0.4.8 only. Ports: fe 3880, be/single 8880, mock IdP 8894.
Scripts, apps and evidence: `../verify_ent/` (= VDEST). Server helper: `VDEST/scripts/srv.sh start <venv> <dev|prod> <src> <label> [ENV=..]` / `srv.sh stop`
(prod = single port 8880 with the real token read from `$SB/secrets`, never written to a file; every app's rxconfig asserts the venv).
The reporter's conversation was not read. All servers, the IdP and browsers were stopped. VDEST has no `rfx_` strings.

| # | claim | verdict | severity | regression | fix in |
|---|---|---|---|---|---|
| 1 | MCPPlugin app dies at `reflex run --env prod` without deploy_url | **CONFIRMED** (with a nuance: 0.10.1 only appeared to work) | high | yes | reflex-enterprise |
| 2 | MCP OAuth consent redirect goes to the backend origin in dev (404) | **CONFIRMED** | medium | yes | reflex-enterprise |
| 3 | AG Grid API / aligned_grids: `ReferenceError: refs is not defined` | **CONFIRMED**; the root bug is a latent rxe bug, which 0.11 widens | high | yes | reflex-enterprise (required); reflex compat shim optional but recommended |
| 4 | `reflex db migrate/init/makemigrations` exit 1 on a fresh rxe app | **NARROWED**: only `db migrate` regressed; `db init`/`makemigrations` fail the same way on 0.10.1; not reproducible without rxe | medium (low-medium) | yes, `db migrate` only | reflex (the new `migrate` call site and the skip-compile bundled-library gap); rxe hardening optional |
| P | PASS: anonymous awaited protected handler (#7782) returns None and does not run | **CONFIRMED PASS** | — | — | — |

### V1. MCPPlugin prod startup ConfigError (deploy_url unset)
```
cd $SB; VDEST/scripts/srv.sh start vent-new  prod VDEST/src/mcpmin i1_new_prod; VDEST/scripts/srv.sh stop     # "[i1_new_prod] server exited"
cd $SB; VDEST/scripts/srv.sh start vent-prev prod VDEST/src/mcpmin i1_prev_prod; VDEST/scripts/srv.sh stop    # ready
# variants: append REFLEX_API_URL=https://myapp.example.com  or  REFLEX_DEPLOY_URL=http://localhost:8880
```
- new: `reflex_base.utils.exceptions.ConfigError: MCP OAuth needs the app's public origin ... neither MCPPlugin(issuer_url=...) nor the config's
  deploy_url/api_url is set`, then `Unexpected exit from worker-1` and `Reflex app stopped` (`VDEST/logs/i1_new_prod_ConfigError.txt`). The stack is
  rxe `post_compile -> _build_server -> _resolve_issuer_url` (mcp.py:1478). It reproduces with MCPPlugin alone, without AuthPlugin, through the anonymous-session issuer path.
- new + `REFLEX_API_URL=https://myapp.example.com`: **same crash**, although the message says api_url is enough. new + `REFLEX_DEPLOY_URL`: starts (`out/i1_new_variants.txt`).
- **Did 0.10.1 actually work?** Only for localhost. 0.10.1 `Config._replace_defaults` derived `deploy_url = http://localhost:<frontend_port>`.
  Prod `_run_prod` calls `_set_persistent(frontend_port=port)`, so rxe advertised `http://localhost:8880`. With `REFLEX_API_URL=https://myapp.example.com`
  (a real single-port deploy that leaves deploy_url unset), 0.10.1 **still advertised** `resource_metadata="http://localhost:8880/.well-known/oauth-protected-resource/_reflex/mcp"`
  (`out/i1_prev_issuer.txt`). `_validate_issuer_security` exempts loopback, so it passed. On 0.10.1 a real deployment without deploy_url/issuer_url therefore
  started with a wrong issuer, and remote MCP clients could not complete OAuth. 0.11 turns that silent misconfiguration into a loud failure. It also breaks
  the cases that did work: local `reflex run --env prod`, and deploys that set only `api_url` (the correct public origin in single-port prod).
- **Changelog coverage:** reflex-base 0.11.0a1 "Breaking Changes" states it plainly: "`deploy_url` now defaults to `None` ... no longer derived from
  `frontend_port`. The new `Config.frontend_url` property ...". The reflex CHANGELOG only mentions it inside the CORS entry ("when `deploy_url` is unset
  (now the default)"). Neither entry warns downstream code that reads `config.deploy_url`.
- **Upgrade exposure:** rxe 0.9.11 declares `Requires-Dist: reflex[db]>=0.9.6` with no cap. Today only `--pre` users get 0.11. Once 0.11.0 final ships,
  `pip install -U reflex` alone breaks every MCPPlugin prod app on all published rxe versions.
- Root cause: rxe `plugins/event_handler_api.py:resolve_server_url()` returns `config.deploy_url` whenever `REFLEX_MOUNT_FRONTEND_COMPILED_APP` is set
  (which is always true in prod single-port, on both versions). Reflex's default change (#7641, reflex-base `config.py:221`) exposes it.
- Fix shape (rxe): in mount mode, return `config.deploy_url or config.api_url`. In single-port prod, api_url *is* the public origin, and it is what
  users set via REFLEX_API_URL. A `frontend_url` fallback would only reproduce 0.10.1's `http://localhost:<port>` guess, so api_url is the better
  fallback. Also fix the error text. `collect_page_info` (`deploy_url or ""`) and the openapi `servers` entry share the cause.
  Reflex-side: no default restore (the CORS change depends on it). Add a reflex CHANGELOG breaking-change line naming `Config.frontend_url` for
  downstream readers of `deploy_url`, and ship 0.11.0 final together with an rxe release carrying the fix (or an rxe `reflex<0.11` cap in the meantime).

### V2. MCP OAuth consent redirect to the backend origin (dev)
```
cd $SB/apps/verify_ent/run; IDP_VENV=vent-idp MOCK_OIDC_PORT=8894 setsid $SB/envs/vent-idp/bin/python -I VDEST/scripts/mock_oidc.py > ../logs/idp.log 2>&1 &
OIDC="OIDC_ISSUER_URI=http://localhost:8894 OIDC_CLIENT_ID=reflex-integration-test OIDC_CLIENT_SECRET=reflex-integration-test-secret AUTHLIB_INSECURE_TRANSPORT=1"
cd $SB; VDEST/scripts/srv.sh start <vent-new|vent-prev> dev VDEST/src/auth_min i2 $OIDC
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python -I VDEST/scripts/mcp_consent_probe.py http://localhost:8880; VDEST/scripts/srv.sh stop
```
`out/i2_consent.txt`: new `authorize -> 302 Location: http://localhost:8880/agent-consent?txn=...` -> **404**. prev `-> http://localhost:3880/agent-consent` -> 200.
new + `REFLEX_DEPLOY_URL=http://localhost:3880` -> 3880, 200. Root cause: rxe `MCPPlugin._resolve_consent_url` (mcp.py:1535) uses `config.deploy_url or issuer_url`,
and in dev the issuer is the backend. On 0.10.1 deploy_url was the frontend origin, which is correct in dev. Fix (rxe): `deploy_url`, else (split
dev/prod) `getattr(config, "frontend_url", None)`, else issuer_url. In mount mode the issuer is already the right origin. No reflex change is needed:
`frontend_url` is the documented replacement.

### V3. AG Grid API `ReferenceError: refs is not defined`
```
cd $SB; for V in vent-new vent-prev; do for M in prod dev; do FP=$([ $M = prod ] && echo 8880 || echo 3880)
  VDEST/scripts/srv.sh start $V $M VDEST/src/agapi i3_${V}_$M && NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python -I VDEST/scripts/agapi_drv.py http://localhost:$FP i3_${V}_$M VDEST/shots; VDEST/scripts/srv.sh stop; done; done
# variants: VDEST/src/agaligned + agaligned_drv.py (aligned_grids); VDEST/src/agapi_memo{,2,3} + agapi_memo_drv.py / agapi_memo_noid_drv.py
```
| app | vent-new | vent-prev |
|---|---|---|
| agapi prod (grid.api.select_all, AgGridAPI.create(id).select_all, getSelectedRows callback) | FAIL 0/0/-1, 6 server-log ReferenceErrors | PASS 3/3/3 |
| agapi dev | FAIL, 6 ReferenceErrors | PASS |
| agaligned dev (resize a column in the top grid) | FAIL: the bottom grid does not follow, 11 page errors `refs is not defined` | PASS (276/276) |
| agapi_memo2 dev (API button in an `@rx.memo` in another module, button has an `id`) | FAIL | PASS |
| **agapi_memo3 dev (same, button WITHOUT an id)** | FAIL | **FAIL on 0.10.1 too** (2 ReferenceErrors) |
- `$/utils/state` still exports `refs` in 0.11.0a1 (`export const refs = {};` at state.js:66, filled by `useRegisteredRef` at :73-75).
- The 0.10.1 import was a side effect of the ref hook. `Component._get_hooks_imports` (reflex-base `components/component.py:1833-1838`) added
  `ImportVar(tag="refs")` whenever the component had an `id`, because the old hook body was `refs['ref_x'] = ref_x`. Any raw `refs[...]` string in the
  same JS module worked by accident. In 0.11.0a1 that same line imports only `useRegisteredRef` (#7694). Compiled `app_components/agapi/agapi.jsx`:
  prev `import {...,mergeSlotProps,refs} from "$/utils/state"` vs new `import {...,mergeSlotProps,useRegisteredRef} ...` (`out/i3_compiled_imports.txt`).
- agapi_memo3 shows the rxe bug is **latent on 0.10.1**: an AG Grid API call in a module with no id'd component fails there identically. 0.11 widens it to every case, including the common one (grid and button on one page).
- Reflex's own code and docs never rely on the implicit import. Every `refs[...]` Var in reflex attaches VarData: `Var._as_ref()` (vars/base.py:1556),
  client_state.py:101, sonner toast.py:34. The upload template imports `refs` explicitly, and `docs/wrapping-react/overview.md` uses `refs` only inside
  `rx.call_script` (evaluated in state.js scope). In rxe, `rxe.map` already attaches `refs_var_data`. The OIDC refresh timer uses `rx.call_script` and is
  unaffected. The rxe sites that break: `aggrid.py:253` (`AgGridAPI._api`) and `aggrid.py:902` (`_format_props` aligned_grids). Third-party libraries
  that hand-write `Var(f"refs['ref_{id}']")` (a plausible pattern, never documented) break the same way. This was not measurable here.
- Which repo: **reflex-enterprise must fix**: attach `VarData(imports={"$/utils/state": [ImportVar(tag="refs")]})` (rxe's own `refs_var_data`) to
  both vars, or build them with `Var(...)._as_ref()`. **Reflex compat shim:** add `ImportVar(tag="refs")` back next to `useRegisteredRef` in
  `_get_hooks_imports`. That is one line, costs one named import per module, and restores the 0.10.1 behaviour exactly for every downstream library.
  I recommend it for the 0.11 line, because published rxe 0.9.11 accepts reflex 0.11 and its users cannot fix this themselves. If the shim is not
  added, the reflex-base changelog should move the `useRegisteredRef` note to Breaking Changes and say that pages no longer import `refs`.

### V4. `reflex db ...` exit 1 on a fresh rxe app
```
cp -r /home/user/reflex-enterprise/demos/ag_grid $SB/apps/verify_ent/src/ag_grid_demo   # copy; never run from the checkout
cd $SB; VDEST/scripts/dbcmd_matrix.sh $SB/apps/verify_ent/src/ag_grid_demo agdemo vent-new vent-prev
```
`out/i4_agdemo_matrix.txt` (fresh copy, no .web, no reflex.db, `REFLEX_DB_URL=sqlite:///reflex.db`):
| cmd | vent-new | vent-prev |
|---|---|---|
| `db migrate` | **exit 1** ValueError (after the upgrade ran) | exit 0 |
| `db init` (alembic dir removed) | exit 1 ValueError | **exit 1 ValueError** (same stack via 0.10.1 `db_init -> _skip_compile(); get_compiled_app()`) |
| `db makemigrations` | exit 1 ValueError | **exit 1 ValueError** |
| `reflex compile` then `db migrate` | exit 0 | exit 0 |
| `reflex run --env prod --backend-only` on a fresh copy (`out/i4_backend_only_fresh.txt`) | dies, same ValueError | **dies, same ValueError** |
- So only `db migrate` regressed (#7742 added `migrations.evaluate_pages()` after the upgrade, reflex/reflex.py:1200). The same underlying failure
  predates 0.11 for `db init`, `makemigrations` and a backend-only start without `.web`. The reporter's "exits 0 on 0.10.1" is true for `migrate` only.
- **Without reflex-enterprise: not reproducible.** `VDEST/src/dyncomp` (pure reflex: Radix components as state vars, a list of them, a computed var
  returning a Radix component, and an rx.Model) gives `db init`/`migrate` (fresh)/`makemigrations` exit 0 on both venvs (`out/i4_pure_reflex_dyncomp.txt`).
  Reflex's dynamic-component serializer never raises on an unbundled library. `_compile_initial_state` bundles the component's imports first, and the
  serializer falls back to a CDN import. The ValueError is rxe's strict check (`reflex_enterprise/vars.py:166 _validate_and_extend_return_expr` via `serialize_lambda`).
- Root cause (reflex, v0.11.0a1): `reflex/compiler/compiler.py:1278-1292`, the `not should_compile` (skip-compile / dry-run) branch. It calls
  `utils._restore_bundled_libraries()` (compiler/utils.py:302), which only reads `.web/<bundled libraries json>` and silently returns when it is missing,
  and then `_compile_initial_state`. It never runs the `plugin.get_frontend_dependencies()` bundling loop of the real compile (compiler.py:1310-1312),
  and the Radix plugin's auto-enable (`enter_component`) does not run either. So on a fresh checkout the bundled list holds only the defaults. The new
  trigger is `reflex.py:1200` -> `migrations.evaluate_pages()` (utils/migrations.py:97-98).
- Workaround (verified, `out/i4_workaround.txt`): `bundle_library("@radix-ui/themes")` at app import makes the fresh `db migrate` exit 0.
- Fix shape: reflex should do one of two things. (a) The `reflex db` page evaluation should not compile the initial state: evaluate_pages only needs
  pages evaluated so lazily imported models register. (b) In the skip/dry-run branch, when no `.web` registry exists, bundle the compiler plugins'
  frontend dependencies (the same loop as compiler.py:1310) before `_compile_initial_state`. (b) also fixes the pre-existing backend-only case. rxe could
  additionally downgrade its check to a warning when no compile populated the list. Severity: medium (low-medium). The DB *is* migrated and only the
  exit status is wrong, but `reflex db migrate && reflex run` in CI/Docker stops there.

### P. PASS re-check: awaited protected handler (#7782), anonymous session
`VDEST/src/auth_min` (a copy of fixture a4auth auth_min) adds the `/await` page. `Vault.secret_action` is a protected `@rxe.event` that returns a value
and records each run. `Pub.call_protected` (`auth=False`) does `r = await Vault.secret_action()`. A positive control `Pub.call_public` awaits an
`auth=False` handler. The probe fields are declared with `rxe.field(..., auth=False)`. Without that, rxe withholds them from anonymous clients and the
probe would read the initial values, which is a pitfall for anyone re-running this.
```
(IdP as in V2) cd $SB; VDEST/scripts/srv.sh start vent-new dev VDEST/src/auth_min pass_await $OIDC
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python -I VDEST/scripts/await_drv.py http://localhost:3880 new_dev; VDEST/scripts/srv.sh stop
```
`out/pass_await.txt`: **[PASS]**. After `call`: result `None`, runs 0, browser sent to `/login?redirect_to=%2Fawait`. Direct protected click: runs 0,
redirected. Control: `'public-value'`. 0 page errors, 0 tracebacks. The claim holds. Dev only; the reporter's prod/2-worker/background/REST legs were
not re-run. Not tested: a backend-internal `(await self.get_state(Vault)).secret_action()`, which is a plain method call and is outside middleware by design.

### Where NOTES.md was insufficient
- Numbering differs between the report and NOTES: report issue 3 (refs) = NOTES "ISSUE 4", and report issue 4 (db migrate) = NOTES "ISSUE 5".
- V2 points to the fixture chain (remap_fixtures, env.sh, fetch_upstream.sh, infra.sh). For auth_min, only `mock_oidc.py`, the app copy and the OIDC env
  vars are needed. The app's rxconfig hard-codes ports 3623/8623, which the CLI flags override.
- V4 claims `db init`/`makemigrations` exit 0 on 0.10.1. They do not. The `enterprise-demo-*` venvs' extra deps (faker==36.2.2, pandas==2.2.3, aiosqlite,
  greenlet from the demo's requirements.txt) are only mentioned in a table.
- `xc.sh`/`repro_mcp_prod.sh`/`agapi_drv.py` hard-code the reporter's `$SB/apps/enterprise` paths and ports 8380/8381. They are re-usable only by editing.
