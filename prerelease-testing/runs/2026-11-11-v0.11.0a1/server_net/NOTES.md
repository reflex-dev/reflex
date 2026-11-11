# server_net — reflex 0.11.0a1 (CORS, lifespan/api_transformer, routes, hydration, CLI shutdown/ports, blocking monitor, otel, hosting-cli)

## Status / resume here
- In progress. Done: harness, prod same-origin smoke, signal shutdown prod (INT group / TERM pid / INT pid, new vs prev).
- Next: dev signals + --json, lifespan matrix, CORS split-origin matrix, routes, HYD-06, #7621, #7653, blocking monitor, otel, hosting-cli.

## Setup (reproduce)
```
export SB=<scratchpad>; export W=$SB/apps/server_net
# own venvs (PyPI only, cwd $SB): reflex[db] + fastapi + uvicorn, siblings pinned to the shared venv's freeze
cd $SB && uv --no-config venv $SB/envs/server_net-main --python 3.12 && \
  uv --no-config pip install --python $SB/envs/server_net-main/bin/python --prerelease=allow --only-binary :all: \
  -c new_constraints.txt 'reflex[db]==0.11.0a1' fastapi uvicorn        # new_constraints = pip freeze of $SB/envs/new
cd $SB && uv --no-config venv $SB/envs/server_net-prev --python 3.12 && \
  uv --no-config pip install --python $SB/envs/server_net-prev/bin/python --only-binary :all: \
  -c prev_constraints.txt 'reflex[db]==0.10.1' fastapi uvicorn          # prev_constraints = pip freeze of $SB/envs/prev
```
- App: `src/netapp` (copy in this dir). Env knobs documented in `src/netapp/netapp/netapp.py` docstring
  (`NA_VENV` guard, `NA_LOG` marks file, `NA_TX` transformer variant, `NA_CASE_DUP`, `NA_EXTRA`, `NA_TASK_FAIL`,
  `NA_TRANSPORT`, `NA_CFG_*_PORT`, `NA_CFG_BLOCK_THRESHOLD`).
- `bin/srv.sh start <label> <venv> netapp <reflex run args>` syncs `src/netapp` to `$W/run/<venv>/netapp` and starts it
  in its own session; `bin/srv.sh stop <label>`; `bin/srv.sh wait <url>`.
- `bin/sigtest.sh <label> <venv> <dev|prod|prod-be|dev-be> <INT|TERM> <group|pid>` = start, signal, report exit time,
  leftover group members, listening ports, and the lifespan marks.
- Driver: `NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python drivers/drv.py <base> <basic|connect|routes|big|block> out.json`.

## Checks
### prod same-origin smoke (single port 3340, server_net-main)
- `drv.py http://localhost:3340 basic`: 11/11 — load, inc, on_load index/about, client nav to `/About` (router path
  `/about`, on_load ran), `/items/A1`, `/ITEMS/b2` (on_load ran with params id=b2, router path `/items/[id]`), upload,
  `rx.download(data=...)`, `rx.download(url=get_upload_url(...))`. Console only a favicon 404.
- anomaly (benign?): the `starlette_app` passed to a lifespan task lists routes
  `/ping, /_health, /_event, /_upload x4, ""` — `/_upload` appears 4 times (POST route + mount, twice). TODO compare prev.
- note: `router.page.path` for `/` is `/index` (check prev).

### signals, prod (`bin/sigtest.sh`, 3342)
| venv | INT->group | TERM->pid | INT->pid |
|---|---|---|---|
| 0.11.0a1 | exits 0.25 s, lifespan stop marks, nothing left | same | same |
| 0.10.1 | same | same | same |

### signals, dev (`bin/sigtest.sh ... dev`, 3342/8342)
- new and prev identical: INT->group, TERM->pid, INT->pid all exit in 0.25 s, lifespan stop marks logged, no leftover
  group members, ports free. No "frontend failed" message on the CLI-requested exit (log ends `Info: Reflex app stopped.`).
- #7624 visible: the `starlette_app` lifespan-task argument is now the inner app (routes `/ping,/_health,/_event,/_upload`),
  on 0.10.1 it was the wrapper (routes `[""]`), as the changelog says.

### `reflex run --json` + slow reader (fixture `fixtures/upgrade/lifecycle/bin/json_matrix.sh`, copied to `$W/fx/upgrade`, FP=3343 BP=8343)
`FP=3343 BP=8343 W=$W/fx/upgrade bash lifecycle/bin/json_matrix.sh <new|prev> <venv> INT-group:40 TERM-pid:40 TERM-pid:6 INT-pid:40`
| spec | 0.11.0a1 | 0.10.1 |
|---|---|---|
| INT-group:40 | exit 6.7 s rc0, 0 invalid, 0 gaps | 6.4 s, same |
| TERM-pid:40 | 7.3 s, 0 invalid | 6.4 s |
| TERM-pid:6 | exit 30.8 s (wall), **0 invalid**, 0 gaps | 30.3 s, **1 invalid (truncated last record), lost_tail 77** (= CLI-27/A3-08) |
| INT-pid:40 | 7.3 s, lost_tail 0 | 9.0 s (exits too; CLI-26/A3-07 no longer reproduces on 0.10.1 either) |
Full output `logs/json_matrix.txt`.

### lifespan / api_transformer (`bin/lifespan.sh <venv> prod-be 8344 <variants>`)
| NA_TX | 0.11.0a1 | 0.10.1 |
|---|---|---|
| fastapi (`FastAPI(lifespan=...)`) | lifespan runs once after the reflex tasks, stops before them; `/api/greet` -> `{"greeting":"hello","client":"connected"}` (app.state + request.state) | lifespan never runs; greet -> nulls |
| fastapi_reg (+ `register_lifespan_task(lifespan)`) | **runs twice** + clear warning "also registered with register_lifespan_task, so it runs twice ... Remove the register_lifespan_task call." | runs once (as a reflex task, `app` = rx.App) |
| starlette | runs, request.state works | never runs |
| callable (pass-through middleware) | receives the lifespan scope, forwards | n/a |
| [fastapi, mw doing `scope["path"]`] (old docs example) | FastAPI lifespan silently skipped: only `Info: ASGI lifespan appears unsupported by <function ...>: KeyError('path')` | lifespan never ran anyway |
| [fastapi, http-only mw that returns on lifespan] | skipped, Info line | n/a |
| list [fastapi, mw] | runs | |
| nested [fastapi /api, fastapi /api2] | both run, ordering inner first, stop reverse | |
| fastapi_fail (lifespan raises at startup) | traceback, `[ERROR] Unexpected exit from worker-1`, **rc=1** (app refuses to start) | starts fine (lifespan never ran) |
| fastapi_shutdown_fail | traceback on shutdown, process exits | |
| fastapi_onstartup (`on_startup=`/`on_shutdown=`) | both run | |
| NA_TASK_FAIL (reflex lifespan task raises) | `[ERROR] ASGI lifespan startup failed`, rc=1 | |
- Upgrade note (by design, in changelog): a FastAPI lifespan that was dead code on 0.10.x now runs; if it raises, the
  app no longer starts. Worth a line in the upgrade guide.
- `app()` now returns `reflex.app._RootMiddleware` (no `.routes/.mount/.add_middleware/.state`): `AttributeError:
  '_RootMiddleware' object has no attribute 'add_middleware'`; 0.10.1 returned a Starlette. The changelog lists this under
  **Performance**, not Breaking (anomaly / docs).
- uvicorn: `REFLEX_ENV_MODE=prod uvicorn --factory netapp.netapp:app --port 8345` with NA_TX=fastapi: startup/shutdown
  complete, all four lifespan marks, `/api/greet` has request.state. OK.

### CORS, prod split origin (`bin/cors.sh <venv> <label> [ENV=VAL]`; static export on 3346 via `python3 -m http.server`, backend `--env prod --backend-only --backend-port 8346`, NA_TX=fastapi)
Static sites: `REFLEX_API_URL=http://localhost:8346 reflex export --frontend-only --zip-dest-dir $W/static/<venv>` then unzip to `site/`.
Raw probe `drivers/cors_probe.py` (httpx + raw-socket websocket upgrade) per Origin; browser `drv.py basic`. Results `res/cors/*.probe.json`, `*.basic.json`.
| label | config | allowed-origin result | other origins | browser (`basic`, 11 steps) |
|---|---|---|---|---|
| A_unset (new) | deploy_url unset (default) | no ACAO anywhere; **WS upgrade 403** | WS 403; no-Origin WS 101 | **6/11: never connects**, 28 websocket opens in ~2 min, toast "Cannot connect to server: websocket error. Check if server is reachable at ws://localhost:8346/_event" (`shots_A_unset/basic_end.png`) |
| B_deploy | `REFLEX_DEPLOY_URL=http://localhost:3346` | ACAO echo + ACAC on /ping /_health /_upload /api/greet + preflights; WS 101 | preflight 400 "Disallowed CORS origin", WS 403 | 11/11 (upload, both downloads) |
| C_wrong | `REFLEX_DEPLOY_URL=https://myapp.example.com` | like A for 3346 | | (not run; same as A) |
| D_star | `REFLEX_CORS_ALLOWED_ORIGINS=*` | any origin reflected incl. `null`, with ACAC true (old behaviour) | | 11/11 |
| E_list | `REFLEX_CORS_ALLOWED_ORIGINS=http://example.com,http://localhost:3346` | allowed | others rejected | 11/11 |
| F_norm | `REFLEX_DEPLOY_URL=HTTP://LocalHost:3346/app/` | normalized to `http://localhost:3346`, allowed | `http://LOCALHOST:3346`, trailing-slash origin rejected (browsers never send those) | 11/11 |
| G_dev_unset (new, dev) | dev mode, unset | any origin (dev unaffected) | | 11/11 |
| P_A_unset (0.10.1) | unset | any origin reflected (incl. `null`) + ACAC | | 11/11 |
- Server-side discoverability: one engineio line `http://localhost:3346 is not an accepted origin. (further occurrences of this error will be logged with level INFO)`; nothing Reflex-specific (no hint at deploy_url / cors_allowed_origins). Browser: only the generic "Cannot connect ... Check if server is reachable" toast and `Unexpected response code: 403` console errors although `/ping` answers.
- Pre-existing, identical on 0.10.1 (benign): `Vary: Origin, Origin, Origin` (three stacked CORSMiddleware layers: inner API, transformer, root); polling GET on a websocket-only server answers 400 with duplicated `access-control-allow-origin: X, X` and `access-control-allow-credentials: true, true` (engineio + Starlette both add them); Starlette adds `access-control-allow-credentials: true` (without ACAO) for disallowed origins — browsers still block, not exploitable. This explains the smoke observation (400 + ACAC for `http://evil.example`).
- `/ping`, `/_health`, `/api/greet` GET from a disallowed origin still return 200 (just unreadable cross-origin) — normal CORS semantics; CORS is not an auth boundary. Non-browser clients (no Origin) can still open the websocket (101).
- Single-port prod opened as `http://127.0.0.1:3347` with default api_url: works (frontend swaps `localhost` for its own hostname). With an explicit `REFLEX_API_URL=http://127.0.0.1:3347` and the page opened at `http://localhost:3347` -> cross-origin -> WS 403, never connects (worked on 0.10.x by construction since any origin was accepted). Edge case of the same breaking change.
- `reflex run --env prod --frontend-port 3347 --backend-port 8347`: "In prod mode, frontend and backend must run on the same port." rc=1 on both versions.

### Documented split deployment (`bin/split_doc.sh`): docs/hosting/self-hosting.md @ v0.11.0a1 lines 63-71
```
reflex run --env prod --backend-only --backend-port 8348
REFLEX_API_URL=http://localhost:8348 reflex run --env prod --frontend-only --frontend-port 3348
```
- 0.11.0a1: page renders, **websocket 403 forever** (10 opens in 20 s), inc never works; backend log "http://localhost:3348 is not an accepted origin". `res/split_doc_new.json`, `res/shots/split_doc_new/`.
- 0.10.1: 3/3 OK. 0.11.0a1 + `REFLEX_DEPLOY_URL=http://localhost:3348` on the backend: 3/3 OK.
- The doc page (and `docker-example/app-platform-backend/README.md`, unchanged since 0.10.1, which tells the user to set only `REFLEX_API_URL` at export time for a CDN-hosted frontend) was not updated for #7641. -> ISSUE.
- Sitemap (export with deploy_url unset, frontend_port unset): `<loc>http://localhost:3000/...</loc>` on both versions (Config.frontend_url fallback) — unchanged; a prod sitemap with localhost links unless deploy_url is set.

### #7599 case-insensitive routes (`NA_CASE_DUP=1`, `drv.py <base> routes`, dev 3349/8349 and prod 3349)
| direct load | 0.11.0a1 dev | 0.11.0a1 prod | 0.10.1 prod |
|---|---|---|---|
| `/About`, `/ABOUT` | about page, on_load ran, router path `/about`, raw path kept | same, HTTP 200 | HTTP 404, page renders about but router path `/404`, **no on_load** |
| `/ITEMS/b2`, `/Items/C3/` | item page, on_load ran with `id=b2`/`C3` (param case kept) | same, HTTP 200 | HTTP 404, router `/404`, no on_load |
| `/nonexistent` | 404 page (HTTP 200 dev) | 404 page HTTP 404 | same |
| client nav `/About`, `/ITEMS/b2` (prod, `basic`) | on_load ran, router path `/about` / `/items/[id]` | | |
| `/Assets/x.js` (prod curl) | | 404 | 404 |
- Two pages differing only in case (`/Foo` + `/foo`): no warning or error at compile on either version. 0.11.0a1: every
  spelling shows the `/Foo` page AND runs `/Foo`'s on_load (consistent; `/foo`'s page is silently unreachable).
  0.10.1: `/foo` renders the `/Foo` page (React Router) but runs `/foo`'s on_load (frontend/backend mismatch); `/FOO` 404.
  -> anomaly/low: a case-colliding `add_page` should be rejected now that matching is case-insensitive (not a regression).
- note: `router.page.path` for `/` is `/index` (pre-existing naming).

### #7670 hosting-cli `reflex cloud config` (own venvs `server_net-hc` = reflex 0.11.0a1 + hosting-cli 0.2.2a1, `server_net-hcold` = + hosting-cli 0.2.1; network blocked with `HTTPS_PROXY=http://127.0.0.1:9`, HOME=scratch)
| case | 0.2.2a1 | 0.2.1 |
|---|---|---|
| no PyYAML | rc=1, stderr "Please install PyYAML ...", no stdout | rc=0 |
| no PyYAML `--json` | rc=1, **no stdout document** | rc=0, stdout `{"generated": false, "path": null}` |
| PyYAML + existing cloud.yml | rc=0 "cloud.yml already exists." (`--json`: `{"generated": false, "path": null}`) | |
| PyYAML, no cloud.yml, no token, `--no-interactive` | rc=1 "Token is required for non-interactive mode." nothing written | |
- PyYAML is not a dependency of reflex/hosting-cli (absent from the shared `new` venv), so the first case is what a
  default install sees. reflex 0.11.0a1 requires only `reflex-hosting-cli>=0.2.1`, so an in-place upgrade keeps 0.2.1
  (campaign-level note in CAMPAIGN_STATE).

### HYD-06 / #7522 pre-connect navigation (fixture `fixtures/hydration/scripts/run_prenav.sh`, WORK=$W/hyd, ports 3350 + proxy 3351)
`WORK=$W/hyd PORT_RANGES="3340-3359 8340-8359" bash $F/scripts/run_prenav.sh <prev|new> <label> 3350 3351` (F = fixtures/hydration); output `logs/prenav.txt`.
| scenario | 0.10.1 (positive control) | 0.11.0a1 |
|---|---|---|
| `/slow -> /other` socket held 2 s | trace `slow_load run1 step1`, `other_load` (LEFT page's on_load ran) | only `other_load#1 path=/other`, slow progress 0 |
| `/items/1 -> /items/2` | `item_load id=1`, `item_load id=2` | only `id=2` |
| `/redir` hijack via 800 ms upgrade-delay proxy (2 runs) | `redirect_load` ran, **final=/other** (hijacked) 2/2 | `item_load id=2`, final=/items/2, 2/2 |
| natural window /items, click delay 0/300 ms (4 runs) | id=1 then id=2 | only id=2 |
| click before connect | processed after load (3/3) | same (3/3) |
-> HYD-06 **fixed**. Behaviour change (intended): on_load of a page left before the socket connected never runs.

### #7621 oversized event (prod 3352, `NA_TRANSPORT=polling|websocket`, `drv.py <base> big`, 2,000,000-char event arg)
- new and prev identical: polling -> the POST gets 400, page keeps working within the 6 s wait (inc after ok, a small
  event after ok, count kept); websocket -> socket dropped and reconnected (2 opens), page keeps working. Could not
  reproduce the pre-fix stall on 0.10.1 with granian + Chromium (the PR's case may need a slower client/proxy).
- anomaly (pre-existing, both versions): the oversized event is dropped silently — no console error, no toast, no
  server log line (contrast: an oversized hydrate shows a clear toast, below).
- `bigstorage` scenario (1.2 MB LocalStorage var, reload): both versions show the toast "Hydration payload (1200396
  bytes) exceeds the server limit (1000000 bytes). Reduce browser storage data and reload." (polling says bytes,
  websocket says characters), page does not hydrate, no reconnect storm (1 open in 20 s) -> the old HYD-05 storm does
  not occur on either version (not my registry item; FYI). `res/shots/bs_server_net-main_polling/bigstorage.png`.

### #7653 `reflex:state-mismatch` (`drivers/mismatch.py <venv> 3353 <none|prevent|observe>`): prod tab open, server restarted with `NA_EXTRA=1` (extra state var)
| mode | 0.11.0a1 | 0.10.1 |
|---|---|---|
| no listener | console.warn "This page was built for another version ... (state schema 3558..., backend e7f4...)", one reload, then works | reloads |
| listener + preventDefault | event detail `{frontend, backend}` hashes; **no reload, no banner**; old bundle keeps working against the new backend (inc ok) | no event; reloads |
| listener without preventDefault | reloads | |
-> pass.

### #7672/#7746 event-loop blocking monitor (dev 3354/8354; `bin/blk.sh <label> <dev|prod> [ENV=VAL]`, `drv.py block`)
- Normal flow (`basic`: nav, on_load, upload, downloads) in dev: **0** blocking warnings; startup: none.
- Default threshold 0.2 s: `short_block` (0.1 s) silent; `ok_async` (await sleep 2) silent; `block_sync` (plain `def`, sleep 1)
  **warns** (sync handlers run on the loop, so this is accurate); `block_async` (time.sleep 2 in async) warns; `cpu_bg`
  (3 s CPU loop in a background task) warns. Each warning names `Event handler S.<name>`, the app file:line, a ~25-line
  stack, then "blocked the event loop for 1.995s in total." (`logs/blk_block_excerpt.log`).
- 3 dev hot reloads, then block_async: exactly 1 warning + 1 total (no leaked monitor threads).
- `event_loop_blocking_threshold=0` (rxconfig): silent. `REFLEX_EVENT_LOOP_BLOCKING_THRESHOLD=1.5`: only block_async + cpu_bg.
  `=abc`: startup fails with a 23-frame traceback ending `EnvironmentVarValueError: Invalid float value: 'abc' for
  event_loop_blocking_threshold`; `=-1`: traceback ending `ConfigError: event_loop_blocking_threshold must be a
  non-negative finite number.` (raw tracebacks: anomaly, generic config path).
- prod: silent (0 warnings for all three).
- reflex-local-auth 0.5.0 (own venv `server_net-la`, fixture `run_la.sh server_net-la dev la-new 3355 8355`; 36/38 + 14/14
  as on 0.10.0 baseline): every login prints `Event handler LoginState.on_submit is blocking the event loop
  (threshold: 0.200s)` + stack ending in `bcrypt.checkpw` (0.27-0.30 s). 7 warnings in one 38-check run. The warning has
  **no app location** (the handler lives in site-packages) and the app developer cannot fix it -> anomaly: accurate but
  not actionable; consider naming the package or suppressing for third-party handlers.

### #7668 / #7635 OTel (own venv `server_net-otel`: reflex 0.11.0a1, reflex-otel 0.2.1a1, reflex-workflow 0.0.1a1, opentelemetry-sdk 1.45.2)
App `src/otelapp` (`ReflexInstrumentor().instrument()` at import), prod 3356, `OTEL_TRACES_EXPORTER=console REFLEX_LOG_JSON=true`, `drivers/otel_drv.py` clicks go / bg / boom.
- `reflex.*` logger and `console.warn` records inside a handler: `trace_id` + `span_id` present; chained event: same
  trace_id, new span_id; background task: own trace; `[Reflex Backend Exception]` error record: has ids. Records at import
  and in a lifespan task: no ids. -> pass.
- anomaly: an app's own logger (`logging.getLogger("otelapp")`) and `print()` are not records of Reflex's JSON handler —
  they arrive as `logger: "stderr"/"stdout"` lines captured by the supervisor, **without** trace ids. Apps logging with
  `logging.getLogger(__name__)` get no correlation. The console span exporter's multi-line JSON becomes one stdout record
  per line (benign).
- #7635: offline check — `reflex_workflow.otel.enabled` False -> `instrument()` True -> second instrument no-op ->
  `uninstrument()` False. A real workflow run was not done (reflex-workflow needs Postgres; not set up in the time box).

### #7693 config ports (`bin/ports.sh <venv>`, rxconfig `frontend_port=3357 backend_port=8357` via NA_CFG_*)
| command | 0.11.0a1 | 0.10.1 |
|---|---|---|
| `--backend-only` | runs on 8357 | exit: "Cannot specify --frontend-port when not running frontend." |
| `--frontend-only` | runs on 3357 | exit: "Cannot specify --backend-port ..." |
| `--backend-only --frontend-port 3358` | exit "Cannot specify --frontend-port when not running frontend." (explicit flag still rejected) | same |
| `--env prod --frontend-only` / `--backend-only` | 3357 / 8357 | exit |
| `--env prod` (both config ports) | exit "In prod mode, frontend and backend must run on the same port." | same (pre-existing; note the Config docstring example itself sets 3000/8000) |

### Double Ctrl-C with stuck lifespan cleanup (`bin/dblint.sh <venv> <dev|prod>`, `NA_SLOW_STOP=60`: lifespan task sleeps 60 s after yield)
- dev (both versions): first INT exits in 2.3 s — granian logs `[WARNING] Killing worker-1 after it refused to gracefully
  stop`; the lifespan cleanup is cut off (`rx_task_stop` never logged; pre-existing).
- prod (both versions): 2nd and 3rd INT (3 s apart) do **not** force the exit; the process waits the full 60 s cleanup,
  no message telling the user it is waiting, then exits. The #7650 force-exit handler is only installed in `_run_dev`;
  the changelog says "`reflex run` ... a later Ctrl-C forces the exit". -> low anomaly (not a regression).

### CLI-16 re-verify (`bin/cli16.sh <venv>`, dev 3357/8357)
- Healthy /ping 200 ~1.5 ms; after a syntax error is appended (hot reload) the backend **refuses immediately**
  (connection refused in ~0.1 ms, no hang) for 15 s; after the fix the first 200 comes back within 1 s; SIGTERM ->
  /ping refused after 0.12 s. Same on 0.10.1. -> still fixed.
