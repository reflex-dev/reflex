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
