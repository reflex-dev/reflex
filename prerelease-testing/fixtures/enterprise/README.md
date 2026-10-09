# fixtures/enterprise — reflex-enterprise on top of reflex

OIDC auth (cross-tab logout, deep links, expiry, MCP, protected client storage, cookie-sync), AG Grid (N-025 and renderer
probes), enterprise demo smoke (AG Grid, dnd, flow, mantine, map, highcharts, tickets) and reflex-azure-auth against a mock IdP.
Curated from the 0.10.0 alpha passes (a5/a4 `*_upgrade_ent/ent`, a3 `a3_ent_auth` + its `verification/`, `a3_ent_grid`,
10-07 `ent_auth`/`ent_grid`, 10-06 `ent_auth_mcp_redis`/`ent_demos`, 10-05 `enterprise/a4`). Expected results below are
the a5 pass records (reflex 0.10.0a5 + enterprise 0.9.7a5 offline wheel) unless marked **[0.10.0]** (re-validated here on
the released reflex 0.10.0 + reflex-enterprise 0.9.7 from PyPI).

## Layout and conventions

```
lib.sh                 sourced by every script: FX (this dir), SB, WORK, ENT_NEW, DRV_VENV, ENT_DRV, IDP_VENV, NP, fx_sync, fx_app, acct_stub
account_stub.py        loopback fictional Reflex Cloud account API so the PyPI enterprise wheel accepts `--env prod` (see Venvs)
auth/  bin/            infra (Redis 8629 + mock IdP 8638), start/stop/wait, seq_* suites, post_sync (N-033), build_ent_drv
       src/            our apps: vauth vauthd vauthx vea entauth mapsapp coregd
       drivers/        vdrv race hunt hunt_cmp storx storx_table deeplink audit_routes vea_drv vea_summ vea_frames coregd_drv json_cmp timeline noise
       scripts/        entauth explorer drivers + launchers (run_app/start_app), a4_matrix, expiry_matrix, prod_suite, xtab_matrix, run_maps
       a4auth/         10-05 auth matrix drivers + auth_min app + minimal anonymous-MCP app; fetch_upstream.sh + lift_app.py
grid/  bin/            start/stop/run (own apps), demo.sh / ag_demo.sh (enterprise demos), fetch_demos.sh, seq_grid, flow_reload_ab, build_demo_venv
       src/            our apps: entv corev aggrid_min entr rxeapp (+ probe.py, copied into entv/corev/entr runs)
       drivers/        drive.py (entv/corev/entr scenarios) summarize anomalies grids
       scripts/        qa_common + demo drivers (smoke_routes, drive_ag_features[_patient], drive_ag_model, probe_state_coldefs,
                       drive_dnd, drive_flow, probe_flow_reload, drive_mantine, drive_highcharts, drive_tickets, api_tickets, drive_rxeapp, probe_aggrid_min)
       demo_overlay/   OUR QA pages for enterprise demos (ag_grid/qa_extras.py, mantine/qa_mantine.py, highcharts/qa_highcharts.py)
azure/ bin/ src/azapp drivers/drive_az.py   reflex-azure-auth against the mock IdP
```

- Scripts run in place from the repo and never write into it: app copies (with `.web`), logs, shots and driver outputs go to
  `$WORK/<auth|grid|azure>/` (default `WORK=$SB/apps/fx_enterprise`). `fx_sync` copies drivers/scripts there first (the
  Python drivers write `../logs`, `../shots`, `../out` next to themselves), `fx_app` refreshes an app copy (keeping its `.web`).
- Venv guards: every server start asserts `reflex` imports from `$SB/envs/<venv>/` (`VENV_GUARD` line 1 of each auth server
  log, `QA_EXPECT_VENV`/`VERIFY_VENV` in the rxconfigs); Playwright drivers assert they run in `$SB/envs/$DRV_VENV/`
  (default `driver`), the a4auth/MCP clients in `$SB/envs/$ENT_DRV/`, the mock IdP in `$SB/envs/$IDP_VENV/`.
- Labels (`L`, e.g. `new`, `rel`) name the app copies and output files, so two builds can be compared side by side
  (`drivers/hunt_cmp.py <L1> <L2>`, `drivers/json_cmp.py`, `drivers/storx_table.py`, `grid/drivers/summarize.py`).
- Run everything from a neutral cwd (e.g. `$SB`), never from a reflex / reflex-enterprise checkout.

## Ports (area range 3600-3639 / 8600-8639; one server set at a time)

| what | ports |
|---|---|
| auth apps (vauth, vauthd, vauthx, vea, entauth) | dev 3620/8620, prod single port 8621 |
| a4auth matrix | auth 3622/8622, auth_min 3623/8623, anonymous MCP backend-only 8626 |
| mapsapp | dev 3624/8624, prod 8625 |
| coregd (core only) | dev 3627/8627, prod 8627 |
| Redis / mock OIDC IdP | 8629 / 8638 (`auth/bin/infra.sh`; the azure fixture uses them too) |
| account stub (prod on the PyPI wheel) | 127.0.0.1:8639 (`lib.sh acct_stub`) |
| grid own apps (`run.sh`) | prod `<port>` in 3600-3605, dev `<port>` + backend `<port>+5000` (entv 3600, aggrid_min 3601, entr 3602, corev 3603, dev 3604/8604) |
| AG Grid demo (`ag_demo.sh`) | prod 3606, dev 3607/8607 |
| other demos (`demo.sh`) | prod 3608, dev 3609/8609 |
| azure | dev 3630/8630, prod 8631 |

`auth/bin/stop_app.sh` also kills any leftover listener on 3620-3639, 8620-8628, 8630-8637; `grid/bin/start.sh` refuses
ports outside 3600-3619/8600-8619.

## Venvs and the enterprise wheel

| env var | default | contents | build |
|---|---|---|---|
| `ENT_NEW` | `new-ent` | reflex (under test) + `reflex-enterprise[mcp]` + `oidc-provider-mock` | `cd $SB && uv --no-config venv --python 3.12 $SB/envs/<n> && uv --no-config pip install --python $SB/envs/<n>/bin/python --prerelease=allow 'reflex==X' 'reflex-enterprise[mcp]==Y' oidc-provider-mock` |
| `ENT_PREV` | — | the previous release pair (`prev-ent` from `scripts/bootstrap_envs.sh`) for back-to-back runs | same |
| `PREV` | `rel` | core-only reflex (coregd / corev controls) | `reflex[db]==<prev>` |
| `DRV_VENV` | `driver` | playwright 1.63 + httpx + websockets | — |
| `ENT_DRV` | `ent-drv` | reflex + `reflex-enterprise[mcp]` + playwright + pytest (a4auth matrix, MCP clients) | `ENT_DRV=<name> auth/bin/build_ent_drv.sh` |
| `IDP_VENV` | `$ENT_NEW` | any venv with `oidc-provider-mock` | — |
| AG Grid demo venv | — | `reflex[db]` + `reflex-enterprise[mcp]` + faker/pandas/aiosqlite | `grid/bin/build_demo_venv.sh <name>` |
| azure venv | `compact-enterprise-az` | reflex + reflex-enterprise + `reflex-azure-auth==0.1.2` | `azure/bin/build_venv.sh` |

**Enterprise wheel.** A run needs EITHER a user-supplied offline enterprise wheel (pre-release builds are not on PyPI; the
`-0offline` wheel the alpha passes used is proprietary — keep it under `$SB/downloads/`, install it by file path
`"<wheel>[mcp]"`, never commit it) OR the PyPI wheel, which gates `reflex run` behind a Reflex Cloud dev login unless
`CI=true` is set. Every start script here exports `CI=true` (it skips the cloud login; it does not change auth behaviour).
The PyPI wheel additionally refuses `reflex run --env prod` / `reflex export` for a logged-out (anonymous) user
(`reflex_enterprise.utils.check_paid_tier_for_command`; the offline wheel reports tier `enterprise` and never asks), and
`CI=true` does NOT lift that. Every prod start here therefore calls `lib.sh acct_stub`: a loopback-only fictional account
API (`account_stub.py`, 127.0.0.1:8639, tier `Pro`, no real credential) wired in through `REFLEX_CLOUD_BACKEND_URL` +
a fake `REFLEX_ACCESS_TOKEN` (the 10-05/10-06 passes used the same fixture). Set `ENT_ACCOUNT_STUB=0` to skip it when
using the offline wheel or a real `reflex login`. The stop scripts stop the stub.

**Enterprise demos and upstream tests are NOT in this repo and NOT in the wheel.** `grid/bin/fetch_demos.sh [<checkout>]` copies
`demos/{ag_grid,dnd,flow,mantine,map,highcharts,tickets}` from a reflex-enterprise checkout (private repo
`github.com/reflex-dev/reflex-enterprise`; `gh repo clone reflex-dev/reflex-enterprise`, check out the tag of the enterprise
release under test; default `$ENT_REPO` or `/home/user/reflex-enterprise`) into `$WORK/grid/demos/` and inserts our QA
overlay imports. `auth/a4auth/fetch_upstream.sh [<checkout>]` copies `tests/integration/{auth_harness,test_auth_flow}.py`
into `$WORK/auth/a4auth/reference/` and lifts `AuthFlowApp` into `$WORK/auth/a4auth/apps/auth/auth/auth.py`.

## Fixtures

| path | exercises | findings | run (from `$SB`; `F=<repo>/prerelease-testing/fixtures/enterprise`) | expected on 0.10.0 / ent 0.9.7 | benign quirks |
|---|---|---|---|---|---|
| `auth/src/vauth` + `auth/drivers/vdrv.py` (`stale`/`away`/`xtab`/`logins`/`storm`/`logoutcookies`), `race.py`, `hunt.py` (`fresh`/`loads`/`relogin`/`pubslash`), `hunt_cmp.py` | OIDC cross-tab logout: stale token-hash at boot (P1 anon bogus hash, P2 signed-in re-assert, P3 cookies cleared + "", P4 live control), logout in tab2 + Back in tab1, two-tab logout race; per-step event / storage-write counts | **N-032** (enterprise reconcile after `hydrate_and_load`, reflex#7493), #7505 echo writes, A3-09 | `$F/auth/bin/seq_ent_auth.sh $ENT_NEW <L> 1` (dev+Redis); `$F/auth/bin/seq_n032_prod.sh $ENT_NEW <L>` (prod 8621, 1 worker); memory: start with `NOREDIS=1` | stale P1-P4 **3/3** each, away **3/3**, xtab **3/3 with 0 accepted-after-logout** (the `race` count varies 0-3/3, always healed by tab2's reconcile); hunt loads: 1 `hydrate_and_load` per boot, `update_vars_internal`+`on_load_internal` on client nav, 0 idle events, 1 cookie sync, 1 hash write per run; relogin ok 2/2 (4 hash writes) **[0.10.0]** | P3 tab may stay on /vault blanked until its next protected click (A3-09); mock-IdP pico.css tunnel error; cookie-sync keepalive `ERR_ABORTED` |
| `auth/src/entauth` + `auth/scripts/drive_auth_redis.py`, `xtab_probe.py`, `stale_hash_probe.py`, `hydration_token_probe.py` | explorer app (AuthPlugin + MCPPlugin, protected/public substates, background tasks): login/logout/re-login cycle, public nav, two tabs, cross-tab logout, stale hash, which boots write the token hash | **N-032**, N-034 (bglive) | `$F/auth/bin/seq_ent_auth.sh $ENT_NEW <L> 2`; `$F/auth/scripts/xtab_matrix.sh 5 $ENT_NEW:<L>` (infra started) | `ALL_PASSED`; `TAB1_LOGGED_OUT 5/5`; `CORRECTED {"anon_boot": [3,3], "loggedin_boot": [3,3], "live_update": [3,3]}`; hydration SUMMARY `{reload_writes: True, newtab_writes: True, garbage_protected: False, garbage_public: False, garbage_id_refresh: False, garbage_all_after_login: True}` **[0.10.0: see Validated]** | the garbage_* flags equal 0.9.12's |
| `auth/scripts/prod_suite.sh` (+ `bglive_probe.py`, `check_mcp_oauth_redis.py`, `check_mcp_anon.py`) | entauth in prod single port + Redis: same suite, background-task liveness on protected states, MCP OAuth + anonymous MCP | N-032, **N-034** (enterprise#263) | `GRANIAN_WORKERS=1 $F/auth/scripts/prod_suite.sh $ENT_NEW <L>` (needs `ENT_DRV`) | ALL_PASSED, 5/5, CORRECTED 2/2x3; bglive `direct` NOT live (pre-existing N-034); MCP pass (a3 record) | 2 tracebacks = the known anonymous protected-resource read |
| `auth/scripts/check_mcp_anon.py --rate`, `check_mcp_oauth_redis.py` on entauth dev Redis | MCP: anonymous tokens, rate limits (61st read, 429 token grants), 2x20 parallel bumps, upload tickets, background tool; OAuth registration/consent/deny/PKCE/refresh rotation/replay/revoke | I-6 (scoped write denied returns `is_error: false`) | infra + entauth dev (part 2 of seq_ent_auth leaves the recipe), then `cd $WORK/auth/scripts && $NP $SB/envs/$ENT_DRV/bin/python check_mcp_anon.py http://localhost:8620 <L> --rate` / `check_mcp_oauth_redis.py http://localhost:8620 http://localhost:3620 <L>` | pass (a3 record; structurally = a2 via `drivers/json_cmp.py`) | — |
| `auth/a4auth/` (`drive_auth.py`, `recheck_reload.py`, `drive_auth_min.py`, `recheck_iframe.py`, `check_mcp_oauth.py`, `check_mcp.py`; apps `auth_min`, `components`, generated `auth`) | the 10-05 auth matrix: 22 upstream auth-flow cases + 3 reload + 4 default + 4 extra-scope + 3 iframe pending replay; MCP OAuth (discovery, registration, consent, PKCE, protected event, code replay, refresh rotation); anonymous MCP (token rejection, events, computed reads, redaction, session isolation) | 10-05 auth items, persist_router_data | `$F/auth/bin/build_ent_drv.sh; $F/auth/a4auth/fetch_upstream.sh <checkout>; $F/auth/bin/infra.sh start; $F/auth/scripts/a4_matrix.sh $ENT_NEW <L>; $F/auth/bin/a4_tally.sh <L>; $F/auth/bin/infra.sh stop` (or `seq_ent_auth.sh ... 3`) | **36/36** + MCP OAuth pass + anonymous MCP pass **[0.10.0]** | `repro_auth_field.py` / `repro_oidc_scopes.py` are the 10-05 a1/a3 repros (run with `$SB/envs/$ENT_NEW/bin/python -I`), now print pass; `components` is a minimal own app (the 10-05 one was an upstream test-app copy; check_mcp only uses AgentState) |
| `auth/scripts/expiry_matrix.sh` + `drive_expiry.py` | token lifetime scenarios on entauth dev+Redis: proactive refresh (75 s tokens, 120 s idle), expired without refresh token, closed tab past expiry, IdP revoke + force_refresh | enterprise expiry behaviour (no ID) | `$F/auth/bin/infra.sh start; $F/auth/scripts/expiry_matrix.sh $ENT_NEW <L> proactive expire_norefresh expire_closed_tab revoke; $F/auth/bin/infra.sh stop` | proactive: refreshed in background, still Alice, `reveal` allowed after 120 s; expire_norefresh: still allowed (pre-existing, userinfo cache); closed tab: new tab logged in (cookie sync refreshes); revoke: still allowed until `force_refresh` -> 400 traceback -> reload -> `/login?redirect_to=%2Fdashboard` | refresh-400 ERROR + traceback (known); `restart_provider` scenario hits JWKS caching (known) |
| `auth/src/vauthd` (+ `vauthd/audit.py`) + `auth/drivers/deeplink.py`, `audit_routes.py` | reflex#7360 router view from enterprise: A deep link with query, B dynamic route, C anonymous client nav, D signed-in client nav, E reload, F logout, G no cookie / HttpOnly token value inside `rx_router_headers`; audit `page_load` routes of every guard decision | #7360 (A5 deep-link probe) | `$F/auth/bin/seq_deeplink.sh $ENT_NEW <L> [dev,prod]` | A-G **3/3** dev+Redis **[0.10.0]**, **2/2** prod+Redis 1 worker; all audit page_load routes on the right page | prod redirects `/vault` -> `/vault/` (307) so prod returns to `/vault/?x=...`; compile prints the intended `State.router.headers.cookie` deprecation (vauthd.py renders it on purpose) |
| `auth/src/vauthx` + `auth/drivers/storx.py`, `storx_table.py` | protected `LocalStorage(sync=True)` + `Cookie` across reload / new tab / client nav / anonymous boot; write counts per boot | **A3-10** (enterprise#274), #7505, F-002 (`hunt fresh`) | `$F/auth/bin/seq_ent_extra.sh $ENT_NEW <L>` (hunt fresh + storx); `NOREDIS=1 $F/auth/bin/run_storx.sh $ENT_NEW:<L>-mem` for memory | kept on reload / new tab; **blanked on client nav with Redis** (A3-10, open); kept with memory; anonymous boot blanks leftovers; `vx_draft` written once per boot, cookie twice | — |
| `auth/src/vea` + `auth/drivers/vea_drv.py` (`storx`/`xsync`/`stale`/`away`/`live`/`stalenav`), `vea_summ.py`, `vea_frames.py` | independent verifier app for A3-10 (all four client-storage kinds, `auth=False` controls, `show_server`) and A3-09; `VEA_INSTRUMENT=1` logs `VEA_FILTER` lines, `VEA_FIX=1` is the causality counter-experiment | **A3-10** (enterprise#274), **A3-09** (enterprise#275) | `$F/auth/bin/seq_vea.sh $ENT_NEW <L> storx,xsync,stale,away 2`; variants `MGR=disk`, `VEA_FIX=1`, `MODE=prod GRANIAN_WORKERS=1` | Redis: storx/xsync -> `""` for draft/plain/ck/ss (backend keeps alice's until next reload, then `""`), `auth=False` controls kept; disk/memory or `VEA_FIX=1`: kept. stale/away: "stay" (blanked on /vault) 3/3, protected click -> /login | — |
| `auth/bin/seq_n033.sh` + `post_sync.sh`, vdrv `logins`/`storm`, `scripts/prod_sync_probe.py` | prod, Redis, DEFAULT granian workers: `POST /_reflex/cookies/sync` on workers that never served a page | **N-033** (enterprise#262) | `$F/auth/bin/seq_n033.sh $ENT_NEW <L>` | fresh server 27/27 **405** across the cold pids; ~3/6 full logins keep their token cookies; storm: failed-sync logins burst POSTs then log out (a3 record; open) | depends on worker count (9 on a 4-CPU box) and warm-up |
| `auth/src/mapsapp` + `auth/scripts/drive_maps.py` | `rxe` map: 200 markers, drag -> State, background ticker, reload restore, base layer/overlay from State, geolocation | — | `$F/auth/scripts/run_maps.sh $ENT_NEW <L>` | dev 16/17, prod 16/17 (the miss: `on_layeradd` never fires, pre-existing) | 54 OSM tile requests blocked by the sandbox proxy |
| `auth/src/coregd` + `auth/drivers/coregd_drv.py` | core-only (no enterprise) `State.get_delta` override sees the boot hydrate | N-032 reflex side | `$F/auth/bin/run_coregd.sh $PREV [dev|prod]` | `GET_DELTA_SAW theme='bogus-boot'` once + `'bogus-nav'` (dev and prod) | — |
| `grid/src/entv` + `grid/drivers/drive.py`, `summarize.py`, `anomalies.py` | AG Grid with State / literal / memo / on_load / detail / lambda-renderer column defs on prerendered routes: s1 full load, s2 reload, s3/s4 events, s5, s6/s7 client nav, s8 `/memo`, s9 `/onload`, s10 second context, s11 `/detail`, s12 `/renderer`, s13 dynamic route; traps the `window.__reflex` setter | **N-025** (enterprise#273) | `$F/grid/bin/seq_grid.sh $ENT_NEW <L> 1`, or `$F/grid/bin/run.sh $ENT_NEW entv prod 3600 entv_<x>_prod [--only s1,s11]`; tables: `cd $WORK/grid && $DRVPY drivers/summarize.py out > out/SUMMARY.md; $DRVPY drivers/anomalies.py out/<run>` | every scenario 2h/6c (state and literal), s8 memo grids 2h/6c, s11 detail headers `Count, Value` x2, s12 3 badges; 1 `hydrate_and_load` in the socket.io connect auth; 0 page errors **[0.10.0]** | AG Grid trial banner, favicon 404 |
| `grid/src/aggrid_min` + `grid/scripts/probe_aggrid_min.py` | minimal State-column-defs grid on load + reload | N-025 | `$F/grid/bin/run.sh $ENT_NEW aggrid_min prod 3601 aggrid_min_<x>_prod` | **4/4 PASS** (`Make, Price`) **[0.10.0]** | — |
| `grid/src/corev` (core only) | a render-time `window.__reflex` reader of an unchanged substate | N-025 reflex side (accepted trade-off, reflex#7492) | `$F/grid/bin/run.sh $PREV corev prod 3603 corev_<x>_prod --only c1` | c1: Untouched / Other / literal `NO_REFLEX`, Touched `HAS_REFLEX` | — |
| `grid/src/entr` (+ `drivers/grids.py`) | enterprise#273 renderer hunt: literal / Var / cond / computed / grouped column defs, lambda renderers, formatters, getters, memo cells, master/detail, pinned rows (r1-r5); `REFLEX_FRONTEND_LAZY_BUNDLED_LIBRARIES=true` | enterprise#273 regression hunt, lazy-bundled-libraries caveat | `$F/grid/bin/run.sh $ENT_NEW entr prod 3602 entr_<x>_prod`; lazy flag: `RUNSUFFIX=_lazy $F/grid/bin/run.sh $ENT_NEW entr prod 3602 entr_<x>_lazy -- REFLEX_FRONTEND_LAZY_BUNDLED_LIBRARIES=true` | r1 6h/24c 8 badges + pinned + group row; r2 all 5 grids, cond 6<->1 cols; r3 `Count, Value` x2; r4 6h/18c; r5 ok; 0 trace renders before `__reflex`; lazy flag: React #130 crash on lambda-Radix pages (known, documented caveat) | `rx.badge(params.value)` shows JSON-quoted value; dev-only AG Grid #306 warning |
| demos via `grid/bin/fetch_demos.sh` + `grid/bin/demo.sh` (`scripts/drive_dnd.py`, `drive_flow.py`, `drive_mantine.py`, `smoke_routes.py`) | dnd kanban (27 checks), React Flow (22), mantine incl. `/qa-mantine` overlay (23), map 4 routes | **N-026** (flow reload reverts controlled edits), **N-028** (`window.onerror` null), F-002 (dnd LocalStorage default) | `$F/grid/bin/fetch_demos.sh <checkout>; $F/grid/bin/seq_grid.sh $ENT_NEW <L> 2` (or `demo.sh $ENT_NEW <demo> prod|dev <L>`) | dnd **27/27** **[0.10.0]**; flow **20/22** (`index lists 6 flow demos` driver expectation + N-026); mantine **23/23** + 1 page error (N-028) **[0.10.0]**; map **4/4** | flow dev drag-timing flakes under load; map tiles blocked |
| `grid/bin/flow_reload_ab.sh` + `scripts/probe_flow_reload.py` | N-026 A/B between two venvs on the flow demo (moved node survives reload?) | N-026 | `ORDER="$ENT_NEW $ENT_PREV" $F/grid/bin/flow_reload_ab.sh 4` | a race on every version (a4 2/4 vs a3 0/4, reversed 3/3 vs 2/3) | — |
| `grid/bin/ag_demo.sh` (+ `demo_overlay/ag_grid/qa_extras.py`; `smoke_routes.py`, `probe_state_coldefs.py`, `drive_ag_features[_patient].py`, `drive_ag_model.py`) | AG Grid demo + QA pages: 20 routes smoke, features, ModelWrapper/SSRM (F-001 enterprise half), State column defs probe | F-001, N-025 | `$F/grid/bin/build_demo_venv.sh <venv>; $F/grid/bin/fetch_demos.sh <checkout>; $F/grid/bin/ag_demo.sh <venv> prod <L>` | smoke **20/20**, features **46/47** (`clipboard gold row0->row4`, driver assumption), model **24/29** (5 pre-existing: SSRM/infinite text filter blank rows, `met` string -> SQLite DateTime), coldefs **7/7** (a3 record) | dev under load: use `drive_ag_features_patient.py`; `/model-auth` AG Grid warning #129 |
| `demo.sh ... highcharts|tickets|rxeapp` (+ `demo_overlay/highcharts/qa_highcharts.py`, `scripts/drive_highcharts.py`, `drive_tickets.py`, `api_tickets.py`, `src/rxeapp` + `drive_rxeapp.py`) | highcharts incl. State-driven `/qa`; tickets demo UI (18 checks) + EventHandlerAPIPlugin HTTP API; `rxe.App` google font + built-with badge (`RXEAPP_BADGE=1` with `REFLEX_SHOW_BUILT_WITH_REFLEX=true`) | **N-027** (openapi.yaml 500 without PyYAML) | `$F/grid/bin/demo.sh $ENT_NEW highcharts prod <L>` etc. | a2-pass record (10-07): highcharts 12/12 dev, 13/13 prod; tickets UI 18/18 + API as recorded (openapi 500 w/o PyYAML, malformed JSON 500, handler errors HTTP 200); rxeapp badge 0 | not re-run since the a2 pass; Highcharts accessibility.js console warning |
| `azure/src/azapp` + `azure/drivers/drive_az.py` | reflex-azure-auth 0.1.2 (generic OIDC; its on_load callback reads `router.url` query params) against the mock IdP: A anonymous deep link `/protected?x=1&y=two` through the on_load chain, B login button, C signed-in client nav | #7360 downstream angle | `$F/azure/bin/build_venv.sh; $F/azure/bin/run_az.sh compact-enterprise-az <L> dev,prod` | A/B/C pass dev + prod (prod returns to `/protected/?x=1&y=two`) **[0.10.0]** | mock-IdP pico.css; `authlib.jose` deprecation |

## How to run the whole area (next pass)

```bash
export SB=<scratch root>  # required
export ENT_NEW=<venv: new reflex + new enterprise[mcp] + oidc-provider-mock> ENT_PREV=prev-ent PREV=prev
F=<repo>/prerelease-testing/fixtures/enterprise; cd $SB
$F/auth/bin/build_ent_drv.sh "<enterprise wheel or req>[mcp]" "reflex==<new>"     # once
$F/auth/a4auth/fetch_upstream.sh <reflex-enterprise checkout>; $F/grid/bin/fetch_demos.sh <reflex-enterprise checkout>
$F/auth/bin/seq_ent_auth.sh $ENT_NEW new 123 > $SB/ent-auth-new.txt   # N-032 vdrv + hunt, entauth suites, 10-05 matrix + MCP
$F/auth/bin/seq_n032_prod.sh $ENT_NEW new; $F/auth/bin/seq_deeplink.sh $ENT_NEW new; $F/auth/bin/seq_ent_extra.sh $ENT_NEW new
$F/auth/bin/seq_vea.sh $ENT_NEW new; $F/auth/bin/seq_n033.sh $ENT_NEW new
$F/auth/bin/infra.sh start; $F/auth/scripts/expiry_matrix.sh $ENT_NEW new proactive expire_norefresh expire_closed_tab revoke; $F/auth/bin/infra.sh stop
$F/grid/bin/seq_grid.sh $ENT_NEW new 12                                # entv N-025 + aggrid_min + dnd/flow/mantine/map
$F/grid/bin/run.sh $ENT_NEW entr prod 3602 entr_new_prod; $F/grid/bin/run.sh $PREV corev prod 3603 corev_prev_prod --only c1
$F/grid/bin/build_demo_venv.sh compact-enterprise-demo "reflex[db]==<new>" "<enterprise>[mcp]"; $F/grid/bin/ag_demo.sh compact-enterprise-demo prod new
$F/azure/bin/build_venv.sh compact-enterprise-az "reflex==<new>" "<enterprise>"; $F/azure/bin/run_az.sh compact-enterprise-az new dev,prod
# the same with $ENT_PREV / label prev for a back-to-back comparison; then compare (hunt_cmp.py, json_cmp.py, summarize.py)
```
Clean up: every script stops its own servers (`auth/bin/stop_app.sh`, `grid/bin/stop.sh`, `auth/bin/infra.sh stop`); delete
`$WORK` (app copies with `.web`/`node_modules`) when done.

## Validated on 0.10.0

Run 2026-10-09 by the curation pass from these reorganized copies through the commands above (`SB` default,
`WORK=$SB/apps/compact_enterprise`, `ENT_NEW=rel-ent` = reflex 0.10.0 + reflex-base 0.10.0 + reflex-enterprise 0.9.7 [mcp]
from PyPI + oidc-provider-mock 0.4.8, `DRV_VENV=driver`, `ENT_DRV=compact-enterprise-drv` built by `auth/bin/build_ent_drv.sh
"reflex-enterprise[mcp]==0.9.7" "reflex==0.10.0"`, azure venv `compact-enterprise-az` = reflex 0.10.0 + enterprise 0.9.7 +
reflex-azure-auth 0.1.2). Every result equals the a5 record; nothing new.

| run | result on 0.10.0 + ent 0.9.7 (PyPI) |
|---|---|
| syntax | `python3 -I -m py_compile` all 114 `.py` (neutral cwd), `bash -n` all `.sh`: clean |
| cheap probes `a4auth/repro_oidc_scopes.py`, `repro_auth_field.py` (rel-ent python, `-I`) | `OIDC scope setup passed`; all four `rxe.field` / `rx.field` vars render |
| `auth/bin/seq_ent_auth.sh rel-ent rel 12` (dev + Redis) | **N-032 fixed**: vdrv stale P1/P2/P3/P4 **3/3 each**, away **3/3**, xtab **3/3, 0 accepted-after-logout** (race 1/3, healed by tab2's reconcile); hunt loads per step = a5 (1 `hydrate_and_load` per boot, `update_vars_internal`+`on_load_internal` on client nav, 0 idle events, 1 cookie sync, 1 hash write per run), relogin ok 2/2 (4 hash writes); entauth `drive_auth_redis` cycle/pubnav/twotab/xtab **ALL_PASSED**, `xtab_probe` **TAB1_LOGGED_OUT 5/5**, `stale_hash_probe` **CORRECTED 3/3 x3**, hydration SUMMARY verbatim the a5 line; 0 tracebacks / 0 TypeError; console noise only mock-IdP pico.css + its 404 and cookie-sync keepalive aborts |
| `auth/bin/seq_ent_auth.sh rel-ent rel 3` (a4auth matrix, dev, memory) | **36/36** (auth-full 22/22, reload 3/3, auth-min default 4/4, iframe 3/3, extra scopes 4/4) + MCP OAuth pass + anonymous MCP pass (minimal own `components` app), 0 tracebacks |
| `auth/bin/seq_n032_prod.sh rel-ent rel` (prod 8621, Redis, 1 worker, account stub) | stale **3/3 x4**, away **3/3**, xtab **3/3, 0 accepted** (race 1/3); 0 tracebacks |
| `auth/bin/seq_deeplink.sh rel-ent rel dev` | A-G **3/3** each; 108 audit records, every `page_load` on the right page (0 stale) = a5 dev |
| `grid/bin/seq_grid.sh rel-ent rel 1` (prod, account stub) | **N-025 fixed**: entv s1-s13 rows of `drivers/summarize.py` **identical to the a5 SUMMARY** (2h/6c everywhere, s8 memo 2h/6c x2, s11 `Count, Value` x2, s12 3 badges); boot = 1 `hydrate_and_load` in the socket.io connect auth, deltas root-only; 0 page errors; aggrid_min **4/4 PASS** |
| `grid/bin/fetch_demos.sh` + `demo.sh rel-ent dnd|mantine prod rel` | dnd **27/27** (0 console/page errors); mantine **23/23** + 1 page error `Cannot read properties of null (reading 'name')` = **N-028 still present** (known); 0 tracebacks |
| `azure/bin/run_az.sh compact-enterprise-az rel dev,prod` | A/B/C **pass** dev and prod (prod returns to `/protected/?x=1&y=two`); 0 tracebacks |

Not re-run here (a5 record stands): expiry matrix, prod_suite / bglive (N-034), MCP on entauth Redis, vauthx `storx` / `vea` (A3-10,
A3-09), N-033 (default workers), maps, coregd/corev, entr + lazy flag, flow/map demos and N-026 A/B, AG Grid demo (needs its own
venv), highcharts/tickets/rxeapp (a2 record only).

**PyPI 0.9.7 vs the a5 offline wheel:** the only behavioural difference met is the prod/export account gate described under
Venvs (offline wheel: tier `enterprise`, no check; PyPI wheel: anonymous -> `reflex run --env prod requires a Reflex account`,
exit, even with `CI=true`) — handled by `acct_stub`. Auth, MCP, AG Grid and demo results are identical.

Fixture fixes made while curating (test code): `a4auth/apps/components` replaced by a minimal own app (its `bump` button
needed `AgentState.bump(1)`: a bare `on_click=AgentState.bump` with an `amount: int` arg is rejected at compile with
`EventHandlerArgTypeMismatchError`, correct framework behaviour); `ENT_DRV` needs `pytest` (the upstream test module imports it);
background launches no longer use `cd ... && setsid ... &` (the subshell held the caller's stdout pipe open).
