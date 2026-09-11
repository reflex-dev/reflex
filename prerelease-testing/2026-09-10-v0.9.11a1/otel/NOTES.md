# Cluster `otel` — reflex-otel 0.1.0a1 + the inert trace points in reflex-base 0.9.11a1

Independent end-to-end exercise of the new OpenTelemetry story in the 0.9.11a1 train:

* reflex-base `reflex_base.otel` (inert trace points, `window.__reflex_otel` frontend hooks) — PR #6899
* `reflex.compile` spans and stage children — PR #6900
* `reflex_otel.ReflexInstrumentor` + `reflex_otel.OtelPlugin` (browser bundle) — PR #6899 / #6901
* reflex #6227 (frontend traceparent, websocket counters/sizes, ASGI wrapping)

Everything installed from PyPI only (`$SB/envs/otel` = reflex 0.9.11a1 + reflex-otel 0.1.0a1 +
opentelemetry-sdk 1.44.0 + opentelemetry-exporter-otlp-proto-http 1.44.0, api/instrumentation
1.44.0 / 0.65b0). Baseline env `$SB/envs/base0910` = reflex 0.9.10.post2. Every run was driven in
real headless Chromium via Playwright with console / pageerror / failed-request / websocket-frame
capture, and the exported telemetry was read back and parsed.

Scoreboard: **31 pass, 9 anomaly, 3 fail (3 distinct issues), 0 skipped.**
No regression against 0.9.10.post2 is possible for the feature itself (the whole surface is new;
`reflex_base.otel` does not exist in 0.9.10.post2 — see `evidence/inertness.txt`).

---

## Layout

```
otelapp/                     the sample app (rxconfig.py + otelapp/{otelapp,telemetry}.py)
scripts/                     every driver / receiver / analysis script used below
logs/                        trimmed server logs (first 400 + last 80 lines of each run)
evidence/                    parsed span trees, metric summaries, console dumps, probe output
screenshots/                 Playwright screenshots per run
```

`otelapp` is driven by three environment variables so one source tree covers every configuration:

| variable | effect |
| --- | --- |
| `OTEL_TEST_MODE` | `programmatic` (build SDK providers in `otelapp/telemetry.py`, dump spans/metrics as JSONL under `$OTEL_DUMP_DIR`), `envvar` (`ReflexInstrumentor().instrument()` with no args, SDK from `OTEL_*`), `off` (no instrumentation) |
| `OTEL_TEST_PLUGIN` / `OTEL_TEST_PLUGIN_ENDPOINT` / `OTEL_TEST_RENDER_TIMING` | add `OtelPlugin(endpoint=..., render_timing=...)` to `rx.Config(plugins=...)` |
| `OTEL_DUMP_DIR` | where the programmatic exporters write `spans-<pid>.jsonl` / `metrics-<pid>.jsonl` |

`GET <backend>/otel/flush` force-flushes both providers and reports
`otel_enabled`, the installed ASGI middleware and the global tracer provider type.

## Reproducing

```bash
SB=/tmp/claude-0/.../scratchpad          # or any scratch dir
APP=$SB/apps/otel/otelapp                # copy of ./otelapp from this directory
OT=$SB/envs/otel/bin                     # reflex 0.9.11a1 + reflex-otel 0.1.0a1 + sdk + otlp-http
DRV=$SB/envs/driver/bin/python           # playwright + websockets
```

All servers below were started from `$APP` with `REFLEX_TELEMETRY_ENABLED=false`.
Ports used: frontend 5180-5188, backend 9580-9588, OTLP receivers 9590 (CORS) / 9591 (no CORS),
redis 9595. Client-side proxy bypass (`NO_PROXY=localhost,127.0.0.1`) is needed for curl,
Playwright **and** — because the OTLP exporter runs inside the server — for the reflex process
whenever the collector is on localhost.

### 1. Inertness without reflex-otel

```bash
$OT/python $SB/apps/otel/scripts/inertness.py $SB/envs/smoke $SB/envs/otel $SB/envs/base0910
```
→ `evidence/inertness.txt`

### 2. Programmatic providers (dev)

```bash
cd $APP
REFLEX_TELEMETRY_ENABLED=false OTEL_TEST_MODE=programmatic OTEL_DUMP_DIR=$SB/dumps/run1 \
  $OT/reflex run --frontend-port 5180 --backend-port 9580 --loglevel debug > run1-dev.log 2>&1 &
NO_PROXY=localhost,127.0.0.1 $DRV $SB/apps/otel/scripts/drive.py http://localhost:5180 $SB/drive/run1 all
curl --noproxy '*' http://localhost:9580/otel/flush
$OT/python $SB/apps/otel/scripts/spantree.py "$SB/dumps/run1/spans-*.jsonl"
$OT/python $SB/apps/otel/scripts/metricsummary.py "$SB/dumps/run1/metrics-*.jsonl"
```
Hot reload: `sed -i 's/rx.heading("otel test app")/rx.heading("otel test app HOTRELOAD")/' otelapp/otelapp.py`

### 3. OTLP receiver + env-var configuration (dev)

```bash
$OT/python $SB/apps/otel/scripts/otlp_receiver.py 9590 $SB/recv/run3 &     # add --no-cors for the CORS test
cd $APP
REFLEX_TELEMETRY_ENABLED=false OTEL_TEST_MODE=envvar \
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
OTEL_SERVICE_NAME=otelapp-env OTEL_TRACES_EXPORTER=otlp OTEL_METRICS_EXPORTER=otlp \
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:9590 OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf \
OTEL_BSP_SCHEDULE_DELAY=1000 OTEL_METRIC_EXPORT_INTERVAL=2000 \
  $OT/reflex run --frontend-port 5181 --backend-port 9581 --loglevel debug > run3-envvar.log 2>&1 &
```
`scripts/otlptree.py "$SB/recv/run3/traces.jsonl"` renders the trace forest,
`scripts/metricsummary.py "$SB/recv/run3/metrics.jsonl"` the instruments.

### 4. Browser tracing (`OtelPlugin`)

Two-phase, because the first compile has to install the pinned `@opentelemetry/*` + `web-vitals`
npm packages **through** the egress proxy while the backend exporter needs `NO_PROXY` for
localhost:

```bash
# phase A - let bun install the frontend deps (no NO_PROXY in the server env)
cd $APP && OTEL_TEST_MODE=off OTEL_TEST_PLUGIN=1 \
  OTEL_TEST_PLUGIN_ENDPOINT=http://localhost:9590/v1/traces OTEL_TEST_RENDER_TIMING=1 \
  $OT/reflex run --frontend-port 5182 --backend-port 9582 ...
# phase B - restart with NO_PROXY + OTEL_TEST_MODE=envvar (command as in step 3, ports 5182/9582)
```
Then `$DRV scripts/drive.py http://localhost:5182 $SB/drive/run4 all` and
`scripts/otlptree.py "$SB/recv/run4/traces.jsonl"`.

CORS failure: start the receiver as `otlp_receiver.py 9591 <out> --no-cors`, point
`OTEL_TEST_PLUGIN_ENDPOINT` at it, and **keep the page open for at least 30 s**
(`scripts/probe_onerror.py http://localhost:5182 25`).

### 5. Prod, multi-worker, auto-instrumentation

```bash
# prod (one port for both)
$OT/reflex run --env prod --frontend-port 5183 --backend-port 5183 --loglevel debug
# prod, 9 granian workers (redis-backed)
redis-server --port 9595 --save '' & REFLEX_REDIS_URL=redis://localhost:9595 REFLEX_LOG_JSON=1 \
  $OT/reflex run --env prod --frontend-port 5185 --backend-port 5185 --loglevel debug
# zero-code path
OTEL_TEST_MODE=off $OT/opentelemetry-instrument $OT/reflex run --frontend-port 5187 --backend-port 9587
```

### 6. API-surface and adversarial checks

```bash
$OT/python $SB/apps/otel/scripts/api_checks.py $OT/python        # -> evidence/api_checks.txt
NO_PROXY=localhost,127.0.0.1 $DRV $SB/apps/otel/scripts/ws_traceparent.py localhost:9587
```

---

## What was verified (all passing unless flagged)

### Inertness (`evidence/inertness.txt`)

* In `$SB/envs/smoke` (no reflex-otel) `import reflex` leaves `sys.modules` with **zero**
  `opentelemetry*` entries; `reflex_base.otel.enabled is False`, `asgi_middleware is None`,
  `_tracer`/`context_api` are unbound, `span()`/`compile_span()` return `nullcontext()`,
  `capture_context()` returns `None`, and the record helpers are no-ops.
* Same result in `$SB/envs/otel` **with** reflex-otel installed but not instrumented — merely
  installing the package imports nothing from opentelemetry at reflex import time.
* No otel-related log lines in any uninstrumented run.
* `reflex_base.otel` does not exist at all in reflex-base 0.9.10.post2 (`ModuleNotFoundError`).
* `window.__reflex_otel` is referenced from exactly four places in the compiled `.web`
  (all optional-chained, so `undefined` is harmless):
  `.web/utils/state.js:424` (`onEventSend`), `:672` (`onSocketConnect`), `:702`
  (`onSocketDisconnect`) and `.web/utils/helpers/upload.js:161` (`onUploadSend`).
  `.web/utils/otel.js` is only written when `OtelPlugin` is in the config.

### Traces (`evidence/run1-spantree.txt`, `run3-spantree.txt`, `run4-spantree.txt`, ...)

* Exactly one span per handler run, named after the event
  (`reflex___state____state.otelapp___otelapp___s.inc`, ...).
* `CONSUMER` for events that arrive over the websocket, `INTERNAL` for chained events, which are
  children of the span that enqueued them. `S.chain` → `Other.h` and `Other.deep` →
  `Other.h` nests three levels deep in one trace, with
  `reflex.event.parent_txid` matching the parent's `reflex.event.txid`.
* `reflex.event.background: true` on `@rx.event(background=True)` handlers.
* A raising handler records an `exception` span event and `STATUS=ERROR: ValueError: boom from
  handler`; the app's `backend_exception_handler` still fires.
* `session.id` is `sha256(client_token)[:16]`; verified numerically
  (`sha256("c6c0647b-98b2-40a8-a858-ca6eef60f413")[:16] == "a9bb50b11ce05dc9"`) and the raw token
  never appears anywhere in the span or metric dumps.
* Websocket URL redaction: the ASGI span for `/_event/` carries
  `url.query = "token=REDACTED&EIO=4&transport=websocket"`; a hand-made
  `GET /_upload?token=SECRETTOKEN123` also comes out as `token=REDACTED`.
* `/ping` produces no span (`curl :9580/ping` → `"pong"`, no span); in prod, `/assets/*.js`
  produces no span either while `GET /` and `GET /favicon.ico` do.
* `reflex.compile` span with `reflex.compile.trigger` / `reflex.compile.dry_run` and the stage
  children `.pages`, `.copy_assets`, `.install_frontend_packages`, `.write`
  (`.evaluate_pages` is the mutually exclusive backend-only branch) — **except for the initial
  compile of `reflex run` in dev, see ISSUE-2.**
* `rx.upload`: browser `PRODUCER` → ASGI `POST /_upload` `SERVER` → handler span, one trace.
* Navigation with `on_load`: `on_load_internal` `CONSUMER` with `S.on_load_second` and
  `set_is_hydrated` as `INTERNAL` children.
* `rx.ComponentState`, `@rx.memo`, `rx.foreach`, `rx.cond` and `rx._x.client_state` all behave
  normally under instrumentation; the two `Counter` instances produce distinct span names
  (`reflex___istate___dynamic____counter_n1.bump` / `..._n2.bump`) —
  `evidence/run11-combo-spantree.txt`, `screenshots/run11-combo.png`.

### Metrics (`evidence/run1-metrics.txt`, `run3-metrics-otlp.txt`, `run10-metrics-autoinstrument.txt`)

All four Reflex instruments plus the ASGI middleware's metrics arrive on every path:

| instrument | observed |
| --- | --- |
| `reflex.event.duration` (s) | per event name, `reflex.event.background`, and `error.type=ValueError` on the failing handler |
| `reflex.state.acquire.duration` (s) | per event name |
| `reflex.websocket.message.size` (By) | `network.io.direction` `transmit` (21 msgs / 7269 B) and `receive` (11 msgs / 1352 B) |
| `reflex.websocket.connections` (`{connection}`) | +1 on connect, back to 0 after the browser closed |
| `http.server.request.duration`, `.request.body.size`, `.response.body.size`, `.active_requests` | scope `opentelemetry.instrumentation.asgi`, stable semconv names |

### Configuration paths

* **Programmatic** `instrument(tracer_provider=..., meter_provider=...)` — works (run1).
* **Env-var** `OTEL_TRACES_EXPORTER=otlp OTEL_METRICS_EXPORTER=otlp OTEL_EXPORTER_OTLP_ENDPOINT=...
  OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf` — works, spans + metrics land in the hand-written
  OTLP/HTTP receiver as protobuf (run3). **Without** `OTEL_EXPORTER_OTLP_PROTOCOL` it fails —
  ISSUE-1.
* **Zero-code** `opentelemetry-instrument reflex run` — works, `otel_enabled: true` with a real
  global `TracerProvider` and no code in the app module (run10).
* A second `instrument()` is a silent no-op even with a different provider
  (`same_tracer: true`); `uninstrument()` turns everything off (`enabled False`,
  `asgi_middleware None`, instruments reset to `_NoOpInstrument`) and a later `instrument()`
  turns it back on.
* `OTEL_SDK_DISABLED=true` leaves the trace points off (`enabled false`, no middleware).
* `excluded_urls=""`, `excluded_urls="/x"`, `OTEL_PYTHON_REFLEX_EXCLUDED_URLS` and the default all
  produce an `ExcludeList` (no `AttributeError` from the < 0.56b0 str bug).
* `OTEL_SEMCONV_STABILITY_OPT_IN` is set to `http` at import of `reflex_otel.instrumentor` and an
  existing value (`http/dup`) is respected.
* `OtelPlugin(sample_rate=...)` rejects `-0.1` and `1.5` with a clear `ValueError`.
* Hot reload keeps working: editing the app source restarts the granian worker, the new worker
  re-instruments, emits a full `reflex.compile` tree with `trigger=hot_reload`, and events keep
  being traced.
* Prod mode (`--env prod`, one port) and prod with 9 granian workers + redis + `REFLEX_LOG_JSON=1`
  both work; no duplicate-instrument warnings, no errors, 10 distinct
  `service.instance.id` values exporting.

### Browser tracing (`evidence/run4-spantree.txt`, `run6-spantree.txt`)

* The plugin writes `.web/utils/otel.js`, prepends `import { OtelRoot } from "$/utils/otel";` to
  `.web/app/entry.client.js`, wraps the hydrate root in `OtelRoot`, adds
  `{ find: "react-dom/client", replacement: "react-dom/profiling" }` to `vite.config.js`
  (only with `render_timing=True`) and writes the `OTEL` block into `.web/env.json`.
* 11 of the 12 outgoing socket.io event frames carry a W3C `traceparent`
  (`evidence/run4-ws-traceparent-frames.json`); the twelfth is the socket.io namespace-connect
  packet, which is not an event.
* Backend event spans become children of the browser `PRODUCER` span, one trace per interaction,
  chained events under them (`otelapp-frontend` → `otelapp-be` in a single trace id).
* Uploads carry the traceparent as an HTTP header: browser `PRODUCER` → `POST /_upload` →
  handler span in one trace.
* `web_vital.TTFB/FCP/LCP/INP/CLS` spans with `web_vital.value` / `.rating` / `.id` /
  `.navigation_type`; 35 `react.render` spans with `react.render.phase` (`mount`/`update`) and
  `react.render.actual_duration_ms`; `socket.connect` (`reflex.socket.connect_count`) and
  `socket.disconnect` (`reflex.socket.disconnect_reason: "io client disconnect"`, correctly
  **not** marked as an error).
* Works identically in `--env prod`.
* `OtelPlugin()` with no endpoint: warning logged at compile
  (`OtelPlugin: no endpoint configured; browser spans are not exported.`), `env.json` endpoint
  `null`, **zero** browser exports, **zero** traceparents on the wire — and this holds even
  though `OTEL_EXPORTER_OTLP_ENDPOINT` was set in that run, confirming the documented
  "no `OTEL_EXPORTER_OTLP_*` fallback" behaviour.
* Collector without CORS headers: the failure is reported through
  `rx.App(frontend_exception_handler=...)` as
  `OtelExportError: OtelPlugin: exporting browser spans to http://localhost:9591/v1/traces
  failed: Fetch request encountered a network error (TypeError: Failed to fetch). A collector on
  another origin must allow CORS requests from this page.` — see ANOMALY-2 for the delay.

### Adversarial client trace context (`evidence/crafted-traceparent-results.txt`)

Events pushed straight onto the socket with crafted fields:

| crafted field | result |
| --- | --- |
| `traceparent` flags `01` + `tracestate` | span joins the client trace / parent span |
| `traceparent` flags `00` | **no span recorded at all** (parent-based sampler honours the client) |
| `baggage=secret=leakme,user=admin` | ignored; `leakme` never appears in the export |
| `traceparent="i-am-not-a-traceparent"` | new root trace, no error |
| `traceparent=12345`, `tracestate={"a":1}` | new root trace, no error |

All five events executed normally. `reflex/app.py` filters the event dict through `_EVENT_FIELDS`
before constructing `Event`, so these fields can never reach a handler.

---

## Issues

### ISSUE-1 (MEDIUM) — the documented env-var setup exports nothing and prints a traceback

`README.md` of reflex-otel and `docs/api-reference/observability.md` both document:

```bash
pip install reflex-otel opentelemetry-sdk opentelemetry-exporter-otlp-proto-http
OTEL_SERVICE_NAME=my_app OTEL_TRACES_EXPORTER=otlp OTEL_METRICS_EXPORTER=otlp \
OTEL_EXPORTER_OTLP_ENDPOINT=http://collector:4318 reflex run
```

`OTEL_TRACES_EXPORTER=otlp` with no `OTEL_EXPORTER_OTLP_PROTOCOL` resolves to `otlp_proto_grpc`
in opentelemetry-sdk 1.44.0, which is not installed by that `pip install` line (the endpoint in
the very same example, `:4318`, is the HTTP port). `_configure_sdk_from_environment()` catches the
`RuntimeError` and logs it with `logger.exception`, then `_instrument()` carries on: the trace
points end up **enabled with the API's `ProxyTracerProvider`**, so nothing is ever exported and
the app looks instrumented.

Repro (exact):

```bash
cd <app>
python scripts/otlp_receiver.py 9590 /tmp/recv &          # any collector; it is never contacted
REFLEX_TELEMETRY_ENABLED=false OTEL_TEST_MODE=envvar \
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
OTEL_SERVICE_NAME=otelapp-readme OTEL_TRACES_EXPORTER=otlp OTEL_METRICS_EXPORTER=otlp \
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:9590 \
  $OT/reflex run --frontend-port 5186 --backend-port 9586
curl --noproxy '*' http://localhost:9586/otel/flush
```

Observed: the terminal gets the full traceback twice (compile process and backend worker) ending
in `RuntimeError: Requested component 'otlp_proto_grpc' not found in entry point
'opentelemetry_traces_exporter'`; `/otel/flush` reports
`{"otel_enabled":true, ..., "global_tracer_provider":"ProxyTracerProvider"}`; the receiver
directory stays empty (`evidence/run9-readme-env-traceback.txt`,
`evidence/run9-receiver-access-EMPTY.log`).
Adding `OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf` (or `OTEL_TRACES_EXPORTER=otlp_proto_http`)
makes exactly the same command work (run3/run4/run10).

Suggested fix: document the protocol variable in both places, and make the failure path either
leave the trace points off or emit a single actionable line instead of a stack trace.

Regression: no (new package). Downstream: no. Changelog: reflex-otel 0.1.0a1 / PR #6899.

### ISSUE-2 (LOW) — the initial `reflex.compile` span tree is lost in dev `reflex run`

The changelog and both docs pages promise "one `reflex.compile` span per app compile ... with the
stages as child spans". For the compile that actually builds the frontend on `reflex run` (dev)
that span tree never reaches the exporter.

`reflex/reflex.py::_compile_app()` runs the initial compile inside
`concurrent.futures.ProcessPoolExecutor(max_workers=1)` when granian is used; a multiprocessing
fork worker exits through `os._exit()`, so `atexit` — and with it
`TracerProvider.shutdown()`/`BatchSpanProcessor.force_flush()` — never runs.

* With `BatchSpanProcessor(schedule_delay_millis=500)` two stage children escaped on the timer and
  arrived as **orphans whose `parent_id` was never exported** — a visibly broken trace
  (`evidence/compile-span-loss.txt`, `evidence/run1-spantree.txt`).
* With the OTLP exporter (`OTEL_BSP_SCHEDULE_DELAY=1000`, and a fortiori with the SDK default of
  5000 ms) nothing from the initial compile arrives at all:
  `grep -c initial recv/run3/traces.jsonl` → `0`, same for run4 and run10.
* `reflex export --frontend-only` (in-process compile) exports the full tree
  (`evidence/export-spantree.txt`), `reflex run --env prod` exports the full `trigger=initial`
  tree (`evidence/run6-spantree.txt`), and a dev hot reload exports the full `trigger=hot_reload`
  tree. Only the dev initial compile loses it.

Mechanism check (no reflex involved):

```bash
python -c "
import atexit, concurrent.futures, os
def child(): atexit.register(lambda: print('ATEXIT RAN')); return os.getpid()
with concurrent.futures.ProcessPoolExecutor(max_workers=1) as ex: print(ex.submit(child).result())
"   # prints the pid; 'ATEXIT RAN' never appears
```

Regression: no (new feature). Downstream: no. Changelog: reflex-base "compile stages" / PR #6900.

### ISSUE-3 (LOW) — adding reflex-otel to a project on the previous stable silently breaks the pin

`reflex-otel` depends on `reflex-base >= 0.9.11a1` but not on `reflex`. `reflex` pins
`reflex-base == <its own version>`, so installing reflex-otel next to reflex 0.9.10.post2 upgrades
`reflex-base` to 0.9.11a1 and leaves `reflex` behind:

```bash
uv pip install 'reflex==0.9.10.post2'
uv pip install --prerelease=allow 'reflex-otel==0.1.0a1'
#  - reflex-base==0.9.10.post2  + reflex-base==0.9.11a1   (no error, no warning)
uv pip check
#  The package `reflex` requires `reflex-base==0.9.10.post2`, but `0.9.11a1` is installed
```

`import reflex` still succeeds, and because reflex 0.9.10.post2's `app.py`/`compiler.py` contain
zero `otel` references the user gets *partial* telemetry (event spans and the state-acquire
metric from reflex-base, but no ASGI middleware, no compile spans, no websocket size/connection
metrics) with nothing pointing at the version skew. Naming `reflex` (or `reflex-base ==`) in
reflex-otel's dependencies, or a "requires reflex >= 0.9.11" line in the README, would make this
an install-time error. Note that `uv pip install 'reflex==0.9.10.post2' 'reflex-otel==0.1.0a1'`
in one command *does* correctly refuse. Evidence: `evidence/mixed-env-0910-plus-otel.txt`.

Regression: no. Downstream: no (packaging metadata of the new package).

---

## Anomalies / benign-but-surprising observations

1. **User-created spans silently disappear when only `instrument(tracer_provider=...)` is used.**
   A handler doing `trace.get_tracer("my.app").start_as_current_span("user.work")` produces
   nothing in the programmatic-provider run, because the app passed its provider to
   `instrument()` but never called `trace.set_tracer_provider()`, so `trace.get_tracer` returns
   the API no-op. In the env-var and `opentelemetry-instrument` runs (global provider installed)
   `user.work` nests correctly under the event span. Worth one line in the docs next to
   "build the providers yourself and pass them".
   Evidence: `evidence/run1-spantree.txt` (absent) vs `evidence/run3-spantree.txt` (present).
2. **The CORS/export-failure report takes ~20-30 s to reach `frontend_exception_handler`.**
   The browser OTLP exporter retries a batch ~5 times before the SDK reports the failure, and
   `otel.js` reports only the first failure per page. A page that is closed sooner (my first
   14 s drive) reports nothing at all even though the browser console is already full of CORS
   errors. Not wrong, but "a rejected collector shows up in the backend terminal" reads as
   immediate. `evidence/run5-frontend-exception-handler.txt`, `scripts/probe_onerror.py`.
3. **Two `net::ERR_ABORTED` requests to the collector at page teardown** in every plugin run
   (`evidence/run4-console.json` / `requests_failed`), from the pagehide flush racing the context
   close. Harmless; no console error and no `OtelExportError`.
4. **N+1 `reflex.compile` spans in prod with N workers.** With redis and 9 granian workers, the
   startup produced 10 `reflex.compile` spans (1 × `trigger=initial`, 9 × `backend_startup`, each
   ~1 ms, no children). By design, but noisy in a real deployment.
   `evidence/run8-spantree.txt`.
5. **The websocket span is named `HTTP /_event/`** (upstream ASGI middleware naming) with
   `url.scheme: "ws"`. Cosmetic.
6. **The upload handler span is `INTERNAL`, not `CONSUMER`.** `S.handle_upload` is a child of the
   `POST /_upload` `SERVER` span, so the "parent is local ⇒ INTERNAL" rule applies. Consistent
   with the implementation, but the docs' "events sent by the frontend are `CONSUMER`" invites
   the opposite expectation for uploads.
7. **PR descriptions #6899/#6901 do not match the shipped code** (they say the frontend event
   span is `SERVER` — it is `CONSUMER` — and that the plugin endpoint falls back to
   `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`/`OTEL_EXPORTER_OTLP_ENDPOINT` — it deliberately does not).
   `README.md` and `docs/api-reference/observability.md` are both correct; only the PR text is
   stale. Flagged because release notes are often assembled from PR titles/bodies.
8. **`REFLEX_LOG_JSON=1` leaves granian's own lines as plain text** (`[INFO] Starting granian
   (main PID: ...)`, `Listening at:`, `Spawning worker-N`, `Started worker-N` — 4 of 100 lines in
   `logs/run7-noendpoint.head.log`). Unrelated to otel, pre-existing granian behaviour, noted
   because it breaks strict JSON-lines parsing of a run that is otherwise clean JSON.
9. **`GET /favicon.ico` 404 in prod** — the sample app ships an empty `assets/` directory, so this
   is the app's own doing, not a framework defect. Recorded only because it is the single console
   error in `evidence/run6-console.json`.

## Cleanliness

Every reflex/granian/vite/bun/redis/chromium/collector process started here was killed; verified
with `ps -eo pid,cmd` at the end of the session (no matches for `otelapp`, `otlp_receiver`,
`redis-server`, ports 518x/958x/9590/9591/9595).

---

## VERIFICATION: reflex-otel's documented env-var setup exports nothing and prints a traceback (missing OTEL_EXPORTER_OTLP_PROTOCOL)

Independent adversarial verification of ISSUE-1 by a second agent, reproduced from the written
repro alone in `$SB/apps/verify2_otel_0/` with a freshly written minimal app (NOT the `otelapp`
multi-mode app) plus a purely in-process repro. Ports 5880 (frontend), 10280 (backend), 10283 /
10282 (collectors).

**VERDICT: CONFIRMED — genuine defect, severity MEDIUM, not a regression, not downstream-breaking.**
Both halves of the claim reproduce exactly, and the defect is *worse* than reported: the
documented example is broken with **either** OTLP exporter package installed (see step 5).

### What was checked, and what it rules out

| refutation attempted | outcome |
| --- | --- |
| environment quirk (proxy / NO_PROXY / port / cwd shadowing) | ruled out — the identical command with one extra variable exports fine on the same ports, same `NO_PROXY`, same collector; every process asserted it ran the `$SB/envs/otel` interpreter |
| API misuse by the claimant's app | ruled out — reproduced with a 20-line app containing only the two lines the docs print, and again with no reflex app at all (in-process script) |
| documented/expected behaviour | ruled out — `OTEL_EXPORTER_OTLP_PROTOCOL` appears **nowhere** on the release branch: `git grep -l OTEL_EXPORTER_OTLP_PROTOCOL origin/r/pre-2026.09.10-34457666442` → no hits |
| pre-existing on 0.9.10.post2 | n/a — `reflex_base.otel` does not exist there (`ModuleNotFoundError: No module named 'reflex_base.otel'` in `$SB/envs/base0910`), so this is new-feature-only, not a regression |
| demo/example-app bug | ruled out — minimal app, no plugins, stock `rx.Config` |
| flaky | ruled out — deterministic, 2/2 app runs and 3/3 in-process runs |

### Exact commands (all run from `$SB/apps/verify2_otel_0/`, `$SB` = the scratchpad root)

```bash
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
D=$SB/apps/verify2_otel_0            # copied to ./verification/verify2_otel_0/

# 1. in-process minimal repro, documented install set ($SB/envs/otel), no protocol variable
cd $D && $SB/envs/otel/bin/python min_repro.py --noproto
#  -> enabled= True   provider= ProxyTracerProvider   span recording: False
#     + the reflex_otel traceback ending in
#     RuntimeError: Requested component 'otlp_proto_grpc' not found in entry point 'opentelemetry_traces_exporter'

# 2. same, with the one missing variable
cd $D && $SB/envs/otel/bin/python min_repro.py --proto
#  -> enabled= True   provider= TracerProvider   span recording: True   (real SDK, exports)

# 3. end-to-end, the documented recipe verbatim (collector on 10283)
cd $D && setsid $SB/envs/otel/bin/python otlp_receiver.py 10283 $D/recv/runA &
cd $D/verifyapp && REFLEX_TELEMETRY_ENABLED=false NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  OTEL_SERVICE_NAME=myapp OTEL_TRACES_EXPORTER=otlp OTEL_METRICS_EXPORTER=otlp \
  OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:10283 \
  $SB/envs/otel/bin/reflex run --frontend-port 5880 --backend-port 10280
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python \
  /home/user/reflex/.claude/skills/prerelease-test/scripts/drive_app.py http://localhost:5880/ \
  --actions '[{"click":"#inc"},{"expect_text":"1"},{"click":"#inc"},{"expect_text":"2"},{"wait":1500}]'

# 4. identical, plus OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf (and BSP/metric delays for speed)

# 5. the other plausible install: the full exporter meta-package instead of the -proto-http one
uv venv $SB/envs/verify2_otel_0 --python 3.11
uv pip install --python $SB/envs/verify2_otel_0/bin/python --prerelease=allow \
  'reflex==0.9.11a1' 'reflex-otel==0.1.0a1' opentelemetry-sdk opentelemetry-exporter-otlp
cd $D && $SB/envs/verify2_otel_0/bin/python min_repro_grpc.py     # same docs env, grpc available
```

### Observed

* **Step 3 (documented recipe):** the `reflex run` terminal prints the full SDK traceback **twice**
  (compile process + backend worker) under the single line `Configuring the OpenTelemetry SDK from
  the environment failed:`, ending in `RuntimeError: Requested component 'otlp_proto_grpc' not
  found in entry point 'opentelemetry_traces_exporter'`. The app starts and works normally
  (Playwright clicked the counter to 2, `RESULT: clean`, zero console errors), but the collector is
  **never contacted at all** — its access log contains only the "listening" line, no `POST`.
  Evidence: `verification/verify2_otel_0/runA-noprotocol-server.log`,
  `runA-receiver-access-EMPTY.log`, `runA-drive.json`, `runA.png`.
* **Step 4 (one variable added):** zero tracebacks, 11 OTLP POSTs, 6 spans in one trace
  (`reflex.compile`, `HTTP /_event/`, `...hydrate`, `...on_load_internal`, `...State.inc`) plus
  metrics. Evidence: `runB-receiver-access.log`, `runB-exported-spans.txt`,
  `runB-protocol-server-grep.txt`, `runB-drive.json`.
  → the entire difference is `OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf`.
* **Step 1/2 (in-process):** `min_repro-NOPROTOCOL.txt` vs `min_repro-WITH-http-protobuf.txt`.
  The no-protocol run ends with `enabled= True`, `provider= ProxyTracerProvider`,
  `span recording: False`, and `force_flush: AttributeError 'ProxyTracerProvider' object has no
  attribute 'force_flush'` — the trace points are on, the ASGI middleware factory is installed, and
  every span is a `NonRecordingSpan`. Contrast the with-protocol run against a dead collector: the
  user gets loud, repeated, actionable `Transient error ... Connection refused` lines. The broken
  configuration is the *quiet* one.
* **Step 5 (NEW — beyond the original claim):** with `opentelemetry-exporter-otlp` (grpc + http)
  installed instead, the docs' example does not fail at startup — it resolves to `otlp_proto_grpc`
  and then speaks gRPC to the HTTP endpoint the same example gives (`:4318`, here `:10283`):
  `StatusCode.UNAVAILABLE ... Failed parsing HTTP/2 (Expected SETTINGS frame as the first frame,
  got frame type 79)`, collector receives nothing. Evidence:
  `verification/verify2_otel_0/min_repro-full-otlp-exporter-grpc.txt`.
  **So the documented recipe exports nothing under both plausible installs**; only the missing
  `OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf` (or `OTEL_TRACES_EXPORTER=otlp_proto_http`) fixes it.

### Mechanism (file:line, installed 0.1.0a1 wheel == release branch)

1. `docs/api-reference/observability.md:11` installs `opentelemetry-exporter-otlp-proto-http`
   only; `:29-30` (and `packages/reflex-otel/README.md:22-23`) then use `OTEL_TRACES_EXPORTER=otlp`
   with an `http://collector:4318` endpoint and no protocol variable.
2. `opentelemetry/sdk/_configuration/__init__.py:188-190` — with no
   `OTEL_EXPORTER_OTLP_TRACES_PROTOCOL`/`OTEL_EXPORTER_OTLP_PROTOCOL`, the alias `otlp` resolves to
   `otlp_proto_grpc` (Python SDK 1.44.0 default; the OTel spec's http/protobuf default was never
   adopted here). `:145` raises `RuntimeError: Requested component 'otlp_proto_grpc' not found ...`
   because that entry point is absent (`entry_points('opentelemetry_traces_exporter')` →
   `['console', 'otlp_proto_http']`).
3. `reflex_otel/instrumentor.py:85-90` — `_OTelSDKConfigurator().configure()` inside
   `except Exception: logger.exception(...)`, which dumps the whole traceback and swallows the
   failure; the function returns `None`, so the caller cannot tell.
4. `reflex_otel/instrumentor.py:196-199` calls it and ignores the outcome, then `:229-233`
   `otel.enable(tracer_provider=None, meter_provider=None, asgi_middleware_factory=...)` runs
   unconditionally → the framework trace points are enabled against the API's
   `ProxyTracerProvider`, i.e. permanently non-recording, with the ASGI middleware installed.
   (`ProxyTracerProvider` never re-resolves here because nothing ever calls `set_tracer_provider`.)
5. For contrast, upstream's own loader logs *and re-raises* on the same failure
   (`opentelemetry/instrumentation/auto_instrumentation/_load.py:176-178`), so
   `opentelemetry-instrument` + `opentelemetry-distro` would abort rather than run blind. Swallowing
   is a deliberate reflex-otel choice; the problem is that it swallows into a state that looks
   instrumented (`reflex_base.otel.enabled is True`) and reports nothing afterwards.
   Note also that in this venv (`opentelemetry-instrumentation` without `opentelemetry-distro`)
   there is no registered `opentelemetry_configurator`, so even the "zero-code"
   `opentelemetry-instrument reflex run` path goes through reflex-otel's fallback and fails the
   same way without the protocol variable — verified.

### Judgement

* **confirmed: yes.** A documented, copy-pasteable quickstart for a package whose only purpose is
  telemetry produces zero telemetry, a scary double traceback, and an app that reports itself as
  instrumented. Two independent agents, two different apps.
* **severity: medium** (agreeing with the claimant). No crash, no data loss, the app is unaffected,
  and the RuntimeError does name the missing component — but the fix is undiscoverable from the
  docs (the variable is not mentioned anywhere in the repo), and the failure mode is silence.
  Cheap to fix before the release: add `OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf` to both
  examples (or switch them to `OTEL_TRACES_EXPORTER=otlp_proto_http`
  `OTEL_METRICS_EXPORTER=otlp_proto_http`), and make `_configure_sdk_from_environment` log one
  actionable line (naming the variable) instead of `logger.exception`, and/or skip
  `otel.enable()` when the requested SDK configuration failed.
* **regression: no.** `reflex_base.otel` does not exist in reflex-base 0.9.10.post2; reflex-otel is
  new in this train.
* **downstream: no.** New optional package at 0.1.0a1; nothing existing breaks.

### Artifacts

`verification/verify2_otel_0/` — `min_repro.py`, `min_repro_grpc.py`, the minimal app
(`verifyapp/`), `runA-noprotocol-server.log`, `runA-receiver-access-EMPTY.log`, `runA-drive.json`,
`runA.png`, `runB-receiver-access.log`, `runB-exported-spans.txt`, `runB-protocol-server-grep.txt`,
`runB-drive.json`, `runB.png`, `min_repro-NOPROTOCOL.txt`, `min_repro-WITH-http-protobuf.txt`,
`min_repro-full-otlp-exporter-grpc.txt`.
The collector used is the claimant's `scripts/otlp_receiver.py` (copied verbatim, it is a test
tool, not part of the system under test).

Cleanliness: every process started for this verification (2 `reflex run` servers, 1 warm-up server,
4 collector instances, Playwright Chromium) was killed; `ps -eo pid,cmd | grep -E
'verifyapp|otlp_receiver|granian|vite|chrom'` is empty.
