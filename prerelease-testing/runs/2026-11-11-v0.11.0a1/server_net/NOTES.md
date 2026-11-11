# server_net — reflex 0.11.0a1 (CORS, lifespan/api_transformer, routes, hydration, CLI shutdown/ports, blocking monitor, otel, hosting-cli)

## Status / resume here
- DONE (2026-11-11). Report: `../reports/server_net.md`. All servers/browsers stopped; ports 3340-3359/8340-8359 free.
- Scratch (full logs, run dirs with .web): `$SB/apps/server_net/` (`logs/`, `res/`, `run/<venv>/netapp`, `hyd/`, `static/`).
- Own venvs: `$SB/envs/server_net-{main,prev,otel,hc,hcold,la}`.
- Not done: real reflex-workflow run (needs Postgres; scratch dir not traversable by the postgres user), Windows/macOS,
  reverse-proxy Host rewriting, enterprise REST/MCP CORS (enterprise cluster).

## Issues (details in the sections below)
1. MEDIUM, regression: documented split deployment (docs/hosting/self-hosting.md "frontend and backend as separate
   processes"; docker-example/app-platform-backend README) never connects on 0.11.0a1 — websocket 403 — because the docs
   were not updated for #7641 (`deploy_url`/`cors_allowed_origins` needed). Repro `bin/split_doc.sh`.
2. LOW, regression: the CORS rejection is hard to diagnose — browser toast says "Cannot connect to server: websocket
   error. Check if server is reachable at ws://..." while /ping works; the server logs one engineio line "X is not an
   accepted origin." (then INFO), no Reflex hint at `deploy_url` / `cors_allowed_origins`. Evidence
   `evidence/shots/cors_A_unset_basic_end.png`, `evidence/logs/cors_server_origin_lines.log`.
3. LOW: case-colliding pages (`/Foo` + `/foo`) are accepted silently; with #7599 one of them is unreachable.
4. LOW: prod `reflex run`: repeated Ctrl-C does not force the exit while lifespan cleanup is stuck (force path only in
   `_run_dev`), though the #7650 changelog says "`reflex run` ... a later Ctrl-C forces the exit". Not a regression.
5. LOW (docs): `rx.App()()` now returns `reflex.app._RootMiddleware` (no Starlette API) — breaking for code using
   `.routes/.add_middleware`, but the changelog files it under Performance only.
Anomalies: blocking-monitor warnings for third-party handlers (reflex-local-auth bcrypt) carry no app location and are
not actionable; app loggers (`logging.getLogger(__name__)`) and print() get no trace ids under REFLEX_LOG_JSON; a
transformer middleware that does not forward lifespan makes Reflex skip the FastAPI lifespan with only an Info line;
oversized events are dropped silently (pre-existing); invalid `REFLEX_EVENT_LOOP_BLOCKING_THRESHOLD` gives a raw
traceback; prod `reflex run` refuses rxconfig `frontend_port`/`backend_port` that differ (pre-existing).

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

### CORS with `transport="polling"` (static export re-made with `NA_TRANSPORT=polling` in `$W/static/server_net-main-poll`; `STATIC=... bin/cors.sh ...`)
- H_poll_deploy (`REFLEX_DEPLOY_URL=http://localhost:3346`): browser 11/11 over polling; polling GET answers 200 with
  ACAO only for the deploy origin. engine.io origin checks are off for polling (`cors_allowed_origins=[]`), so a polling
  session is created for any Origin (unreadable cross-origin; same as before).
- H_poll_unset: never connects; 53 failed requests in ~2 min; browser console has the clear Chromium message "blocked by
  CORS policy: No 'Access-Control-Allow-Origin' header"; nothing in the server log.

## Artifacts in this dir
`src/netapp`, `src/otelapp` (apps), `bin/*.sh` (runners), `drivers/*.py` (Playwright / raw probes), `evidence/logs`
(json matrix, lifespan matrices, prenav, blocking excerpts, otel JSON records, lifespan-fail rc=1 log, CORS origin
lines), `evidence/res` (probe/driver JSON), `evidence/shots` (CORS rejection toast, documented split deployment,
hydration-too-large toast), `new_constraints.txt` / `prev_constraints.txt` (freeze of the shared venvs used as -c).

## VERIFICATION
Independent verifier `verify_net` (2026-11-11). I reproduced everything from the written repro and the doc text, not from
the reporter's scripts. Own venvs (PyPI only, cwd `$SB`): `$SB/envs/vnet-new` = `reflex==0.11.0a1 fastapi uvicorn`
(`--prerelease=allow --only-binary :all:`), `$SB/envs/vnet-prev` = `reflex==0.10.1 fastapi uvicorn` (no prerelease flag).
Both resolve starlette 1.10.0 and python-engineio 4.15.1, so engine.io is held constant. My probe app is
`verify_net/src/vapp` (a counter, plus `VN_CASE_DUP=1` and `VN_TX=fastapi|old_mw|new_mw|http_only_mw`). Scripts are in
`verify_net/bin/`, evidence in `verify_net/evidence/`. Ports used: 3840-3851 and 8840-8845. Every server, proxy and
browser was stopped, and the ports were checked free at the end.

Where these NOTES fell short: the split-deployment repro depends on `bin/srv.sh` and `drivers/drv.py`, so it cannot be
rerun from the doc text alone. That was easy to replace. The NOTES never tested a TLS-terminating proxy in front of a
*same-origin* deployment (NOT_COVERED), and that case turned out to be the larger half of issue 1 (below). The double
Ctrl-C item was not in my brief and I did not re-verify it.

### V1. Split deployment 403. CONFIRMED, and WIDER: severity raised to HIGH (regression)
- Literal doc repro (`bin/split.sh <venv> <label> <FP> <BP> [backend ENV=VAL]`): `reflex run --env prod --backend-only
  --backend-port 8840`, then `REFLEX_API_URL=http://localhost:8840 reflex run --env prod --frontend-only --frontend-port 3840`,
  then Chromium clicks inc twice:
  | run | result |
  |---|---|
  | 0.11.0a1 (`split_new`) | count=0, 13 websocket opens, each `Unexpected response code: 403`; toast "Cannot connect to server: websocket error. Check if server is reachable at ws://localhost:8840/_event"; backend logs one line `http://localhost:3840 is not an accepted origin. (further occurrences ... INFO)` |
  | 0.10.1 (`split_prev`) | count=2, 1 websocket open |
  | 0.11.0a1 + backend `REFLEX_DEPLOY_URL=http://localhost:3842` | count=2 |
  | 0.11.0a1 + backend `REFLEX_CORS_ALLOWED_ORIGINS=http://localhost:3843` | count=2 |
- NEW, not in the original report: a same-origin single-port prod server behind a TLS terminator also never connects.
  The self-hosting doc says (L91-95) "a single-port production deployment behind a TLS-terminating proxy needs no
  `api_url` configuration at all". `bin/tls_run.sh <venv> <label> <P> <TLS_P>` starts `reflex run --env prod` on P with
  `REFLEX_API_URL=https://vnet.test:<TLS_P>`, puts `bin/tls_term.py` in front (TLS, then raw TCP passthrough; it keeps
  Host and adds no X-Forwarded-*), and loads `https://vnet.test:<TLS_P>/` in Chromium:
  | run | result |
  |---|---|
  | 0.11.0a1 (`tls_new`) | count=0, 12 websocket opens, all 403; `https://vnet.test:3845 is not an accepted origin.` (`evidence/tls_new.png`) |
  | 0.10.1 (`tls_prev`) | count=2 |
  | 0.11.0a1 + `REFLEX_CORS_ALLOWED_ORIGINS=https://vnet.test:3849` | count=2 |
  Raw handshakes against single-port prod 0.11.0a1 (`bin/ws_origin.sh`, `evidence/ws_origin_new.txt`):
  `Host app.example.com, Origin https://app.example.com` gives 403; adding `X-Forwarded-Proto: https` gives 101; with
  `X-Forwarded-Proto: http` it is 403 again. `Origin http://127.0.0.1:3844` against `Host localhost:3844` also gives 403.
- Root cause @ v0.11.0a1: `reflex/app.py:512-515` (`_cors_allowed_origins` returns `None` in prod when `deploy_url` is
  unset) passes through `reflex/app.py:761-766` to `AsyncServer(cors_allowed_origins=None)`. engine.io then accepts only
  `{wsgi.url_scheme}://{Host}` plus the `X-Forwarded-Proto`/`X-Forwarded-Host` variant
  (`engineio/base_server.py:284-300`, enforced in `engineio/async_server.py:227-236`). The scheme comes from the ASGI
  scope, and that is `http` behind any proxy that terminates TLS. So "same origin" fails unless the proxy sends
  `X-Forwarded-Proto: https` (and keeps Host, or sends X-Forwarded-Host). The new default itself is intended (#7641 is
  labeled security + breaking, and configuration.md L101-112 documents it). The deployment guides were not updated.
- Deployment guides at the tag:
  - `docs/hosting/self-hosting.md` L63-71 (split `--backend-only`/`--frontend-only`): broken (reproduced).
  - `docs/hosting/self-hosting.md` L89-109 "API URL" (static host + `api_url`) and L135-152 "Exporting a Static Build"
    (`REFLEX_API_URL=https://api.example.com reflex export`): broken, because the frontend is on a different origin from
    the backend and no `deploy_url` is set.
  - `docs/hosting/self-hosting.md` L84-87 "Reverse Proxy and Websockets" and L91-95 ("behind a TLS-terminating proxy needs
    no api_url"): broken unless the proxy forwards `X-Forwarded-Proto` (reproduced with a passthrough terminator). The
    page never mentions forwarded headers.
  - `docker-example/app-platform-backend/README.md` L58-67 (CDN frontend plus `REFLEX_API_URL` only): broken (the same
    shape as the static export).
  - `docs/hosting/scaling.md` L62-72 (frontend on a CDN, backends behind a load balancer, `--backend-only`): broken.
    It says to configure only the API URL.
  - `docker-example/production/` (Dockerfile + Caddyfile, "Start here", "use with an existing load balancer or reverse
    proxy to terminate TLS ... Render or Heroku"): likely broken behind the platform's TLS edge. Caddy keeps Host but by
    default replaces an untrusted incoming `X-Forwarded-Proto` with its own scheme (`http`), and the Caddyfile sets no
    `trusted_proxies`. That is exactly the 403 row above. Not run end to end: downloading a Caddy binary was refused in
    this sandbox. Plain `docker run -p 8080:8080` over http is fine.
  - `docker-example/production-compose/`: OK. Caddy terminates TLS itself, so `X-Forwarded-Proto: https`.
  - Other docs/hosting/* pages (Reflex Cloud: deploy-quick-start, config_file, custom-domains, regions, ...): n/a.
    reflex.dev hosting sets these values itself; not verified.
- Verdict: CONFIRMED as a regression, and broader than reported. Every documented cross-origin self-host recipe breaks,
  and so do TLS-terminating proxies that do not send `X-Forwarded-Proto: https`. I put this at HIGH, not medium. The
  0.11.0a1 changelog does state the change, but a user who follows the deployment docs gets an app that never connects,
  with an error that points elsewhere (V2). The behaviour is intended (security), so the default should not go back to
  `*`. Before final:
  (a) Docs (required): self-hosting.md split, static export and API URL sections, scaling.md, and the app-platform-backend
      README should set `REFLEX_DEPLOY_URL=<frontend origin>` (or `REFLEX_CORS_ALLOWED_ORIGINS`) on the *backend*. The
      reverse-proxy section needs `X-Forwarded-Proto` (nginx `proxy_set_header X-Forwarded-Proto $scheme; Host $host`),
      and docker-example/production's Caddyfile needs a note on `trusted_proxies`/`header_up X-Forwarded-Proto`. The
      upgrade guide should get a line too.
  (b) Code (recommended): treat the `None` default as "same origin *or* the forwarded scheme". Pass engine.io a callable
      `cors_allowed_origins` that also accepts `https://{Host}` when the request arrived as http (or compare host only:
      a cross-site page cannot forge Origin, so host equality keeps the protection; the cost is accepting an http page
      of the same host). That fixes the TLS
      proxy case without reopening CORS. Defaulting to `REFLEX_API_URL` for `--frontend-only` cannot help: that process
      is not the one checking origins. The backend could warn at startup, but only when `--backend-only` and
      `deploy_url`/`cors_allowed_origins` are both unset, and docker-example/production also runs `--backend-only`
      same-origin, so an unconditional warning would be noise there. Prefer the rejection-time hint in V2.

### V2. CORS rejection reported as "server unreachable". NARROWED: low, a diagnosability gap of #7641 (the message itself is pre-existing)
- Reproduced in both runs above (`evidence/split_new.png`, `tls_new.png`). The page and `/` answer 200 while every
  websocket gets 403. Server side there is exactly one WARNING-level engine.io line per process, `<origin> is not an
  accepted origin. (further occurrences ... INFO)`, and nothing from Reflex. The toast text comes from
  `packages/reflex-components-core/src/reflex_components_core/core/banner.py:80-91` (`default_connection_error`) and
  `:107-110`. It is byte-identical at v0.10.1, so the message did not regress; what is new is a default that triggers it.
  The browser WebSocket API does not expose the 403 status to JS, so the frontend cannot tell the cases apart from the
  socket error alone. No Reflex-level hint names `deploy_url` or `cors_allowed_origins` anywhere (grep of reflex/,
  reflex-base and the templates at the tag).
- Fix shape: (1) Backend: give engine.io a callable `cors_allowed_origins` (Reflex's own same-origin check, see V1b). On
  rejection it logs once at WARNING: "Rejected websocket from origin X (backend sees Y). In prod only same-origin
  connections are accepted unless deploy_url or cors_allowed_origins is set; set REFLEX_DEPLOY_URL=X on the backend, or
  forward X-Forwarded-Proto from your proxy." (2) Frontend (optional): after N failed websocket opens,
  `fetch(pingUrl, {mode: "no-cors"})`. If it resolves, the backend is reachable, so show "server reachable but refused
  the connection (check deploy_url / cors_allowed_origins)" instead of "Check if server is reachable".

### V3. Case-colliding pages. NARROWED: low, NOT a regression (pre-existing; 0.11 changes which page wins)
- Backend router (`bin/case_router.py`, no server): 0.11.0a1 resolves `/Foo`, `/foo` and `/FOO` to `Foo`. On 0.10.1
  `/Foo` goes to `Foo`, `/foo` to `foo`, and `/FOO` to None.
- Browser, prod single port, `VN_CASE_DUP=1` (`evidence/case_new.json`, `case_prev.json`):
  0.11.0a1: all three spellings give HTTP 200, the Foo-upper page, and the Foo-upper on_load.
  0.10.1: `/foo` gives the **Foo-upper page with the foo-lower on_load** (frontend/backend mismatch); `/FOO` gives HTTP
  404 with the Foo-upper page and no on_load.
  So the `/foo` page was already unreachable on 0.10.1, because React Router matches case-insensitively. 0.11.0a1 makes
  the backend agree with the frontend. No warning at compile or start on either version.
- Root cause @ v0.11.0a1: `reflex/app.py:1295` (`_register_prepared_page`) compares route strings exactly, and
  `_check_routes_conflict` (`reflex/app.py:1594`) only checks dynamic segment names. `reflex/route.py:185` compiles the
  route regex with `re.IGNORECASE`, and `get_router` (route.py:198-208) returns the first match by specificity, which
  for ties is registration order.
- Fix shape: in `_register_prepared_page` (and `_check_routes_conflict` for evaluated pages), raise `RouteValueError`
  when `route.casefold()` (ASCII) equals an existing route with different case. Keep a casefolded-route dict so the
  check stays O(1).

### V4. `rx.App()()` returns `_RootMiddleware`. CONFIRMED: low; breaking by design, filed in the wrong changelog section
- `bin/lifespan_probe.py` (in process, `REFLEX_ENV_MODE=prod`): 0.11.0a1 returns `type(app()) = reflex.app
  _RootMiddleware` with `add_middleware/routes/mount` all False. 0.10.1 returns `starlette.applications Starlette`,
  all True (`evidence/lifespan_probe.txt`).
- Root cause: `reflex/app.py:1010-1023` (`__call__` returns `_RootMiddleware`, or the otel wrapper), class at
  `reflex/app.py:364`. CHANGELOG.md L69 lists it under Performance. The Breaking section (L3-15) does not mention it,
  and the related `starlette_app` lifespan-argument change sits in the Bug Fixes entry at L54.
- Downstream reliance is unlikely. reflex-enterprise 0.9.11 (`$SB/envs/new-ent` wheel) never uses the return value of
  `app()`. It calls `app._api.add_middleware` / `app._api.routes.insert` / `app._api.mount` (auth.py:577,
  mcp.py:1830/1883/1957, api_tokens.py:527, cookie.py:383), and `_api` is still a Starlette. `app.add_middleware` in
  auth.py:343 is Reflex's event middleware. proxy.py's `proxy_middleware` gets the lifespan `starlette_app` (now
  `_api`, still a Starlette), not `app()`. The docs at v0.10.1 and v0.11.0a1 have no `app()` /
  `app.__call__` / `.add_middleware` usage, and reflex-examples has none either. What breaks is only user code like
  `asgi = app(); asgi.add_middleware(...)`, `asgi.routes`, or `isinstance(asgi, Starlette)`. Mounting `app()` inside
  another ASGI app or server still works.
- Fix: move or duplicate the L69 entry into Breaking with the migration ("use `api_transformer` or `app._api` ... to add
  Starlette middleware or routes"). No code change.

### V5. Lifespan skipped by a middleware that breaks on lifespan scopes. CONFIRMED anomaly: low, not a regression (a new feature degrades silently; documented)
- Real server `bin/be_tx.sh <venv> <VN_TX> <BP>` (`reflex run --env prod --backend-only`, default loglevel), then
  `GET /api/greeting`:
  | VN_TX | 0.11.0a1 | 0.10.1 |
  |---|---|---|
  | `fastapi` | `{"greeting":"hello","client":"connected"}`, lifespan start/stop marks | (probe) nulls, never runs |
  | `old_mw` = `[fastapi_app, mw doing scope["path"]]` (docs @ v0.10.1 overview.md:132) | nulls; only `Info: ASGI lifespan appears unsupported by <function old_mw.<locals>.middleware at 0x...>: KeyError('path')` | nulls (never ran) |
  | `new_mw` = docs @ v0.11.0a1 overview.md:129-139 (`scope.get("path")`) | **works**: hello/connected, start + stop marks | nulls |
  | `http_only_mw` (returns on non-http scopes) | nulls; Info line `...: no answer` | nulls |
  HTTP requests still go through the broken middleware fine (`Request: /api/greeting` printed), so the app works apart
  from the lifespan.
- Root cause: `reflex/app_mixins/lifespan.py:120-132` (`_run_asgi_lifespan`). Any exception raised while answering
  `lifespan.startup` becomes `{"type": repr(err)}`, and `logger.info(...)` records it as "appears unsupported". This
  mirrors uvicorn's `lifespan="auto"`. `reflex/app.py:987-1007` hands the FastAPI transformer's lifespan only to the
  outermost wrapped app (`lifespan_apps` gets the callable-wrapped app, not the inner Starlette), so one broken
  middleware hides every Starlette lifespan below it.
- Assessment: the outcome is identical to 0.10.1 (the lifespan never ran), so nothing a user had breaks. The new docs
  state the skip ("An app that does not support lifespan events is skipped, and Reflex logs that it appears not to
  support them", overview.md:185-188), and the updated example works. The changelog's promise does not hold for anyone
  who copied the 0.10 docs middleware, though, and an INFO line that calls a `KeyError` "unsupported" is easy to miss.
  Low.
- Fix shape: when startup *raises* (not just returns without answering), log at WARNING with the exception, and name
  the Starlette/FastAPI transformer(s) under it whose `router.lifespan_context` is not the default, because their
  lifespan will not run. Or fall back to sending lifespan events directly to those inner Starlette transformers, as is
  already done for mounted ones. An upgrade-guide line: "middleware in `api_transformer` now sees `lifespan` scopes; use
  `scope.get("path")` or pass non-http scopes through."
