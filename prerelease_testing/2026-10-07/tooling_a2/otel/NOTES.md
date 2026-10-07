# OpenTelemetry: actual local exports and browser recovery

**Final result:** 116/116 strict checks passed across development/production and Chromium/WebKit, including fresh linked browser/backend exports on the existing page after collector restoration, before reloading. Supplementary original runs contribute another 104 passing assertions: 220/220 total over eight browser executions. These repeat 29 final checkpoint types; they are not 220 distinct features. No new functional issue was found.

## Published setup

`reflex==0.10.0a2`, `reflex-otel==0.2.0a1`, Python **3.11.16**, macOS 26.6.2 arm64. The plugin's published metadata requires Python **>=3.11**; successful execution uses that minimum minor. No Python 3.10 plugin runtime is claimed. SDK/API and the explicitly installed, documented HTTP/protobuf exporter are **1.45.1**; instrumentation packages use their normal beta-version scheme, **0.66b1**. Full Python graph: `environment/alpha2.txt`, package origins/platform in every `run.json`. The graph was frozen after installing the exporter, then remained read-only. No installed framework came from this checkout.

The app uses the public APIs in the published wheel's README (`environment/plugin-metadata.txt`): `ReflexInstrumentor().instrument()` in the app, standard `OTEL_*` SDK configuration, and `OtelPlugin(endpoint=..., render_timing=True)` in `rxconfig.py`. Instrumentation is called twice to exercise documented idempotence. One handler span per pre-outage add/audit/background/failure event is independently counted by `summarize.py`; no provider-override or duplicate-instrumentation warning appeared.

Node **26.8.1**, managed Bun **1.4.0**, React **19.3.0**; frontend plugin pins include `@opentelemetry/api@1.9.1`, core/resources/sdk-trace-web **2.10.0**, OTLP browser exporter **0.221.0**, web-vitals **6.1.1**. `environment/frontend-dependency-graph.json.gz` retains the complete resolved Bun graph (266 entries), normalized by removing JSON trailing commas only. The original lock hash and package.json are retained separately; no generated app/node_modules directory is included. Driver: Python 3.12.14, Playwright 1.63.0, Chromium 153.0.8010.12 and WebKit 26.6; exact driver freeze retained.

## Local collector contract

`collector.py` serves only **127.0.0.1:8588**, accepts CORS browser requests at `http://localhost:8588/v1/traces`, and decodes actual browser OTLP JSON and backend OTLP protobuf into append-only JSONL. It returns the corresponding empty success response. Full decoded request bodies, content type, origin, public header, byte size and receipt time are retained in gzip. HTTP logs retain successful POST/OPTIONS and readiness requests. No SDK/exporter is mocked; the minimal local receiver replaces a hosted collector, not browser or backend instrumentation.

Frontend 3586/backend 8586 are used in development; production uses 8586 for both. `qa-frontend` and `qa-backend` resource services distinguish browser/backend spans. The configured frontend header is explicitly public test data (`x-qa-collector: public-fixture`). Backend settings are `OTEL_TRACES_EXPORTER=otlp`, `OTEL_METRICS_EXPORTER=none`, `OTEL_LOGS_EXPORTER=none`, `OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf`, endpoint `http://localhost:8588`, timeout 1 second and batch schedule 200ms. Those settings bound the test, not a performance claim.

The host had **no inherited OTEL_* settings** (recorded without reading any credential values). The final replay runner additionally drops any inherited OTEL_* settings before adding this local configuration, preventing a trace-specific endpoint/header override on another machine. That replay hardening and metadata recording were added after runs; `run_case_strict_executed.py` preserves the exact strict runner used. No production collector, hosted account, user credentials or external telemetry destination was configured.

## Browser journey and evidence

Each browser starts a fresh session, fills a synthetic marker into state, and performs three add events, their chained audit events, one background job (three increments), a route change, and an intentional `ValueError` handled with a toast. Add/audit remain synchronized; a later click proves recovery after the handled error.

The collector process is then actually stopped, producing **connection refusal**. The user performs two further adds and another background job; the UI remains usable after export errors occur. The collector restarts, the sixth add is sent, and the strict check waits for a **new** browser PRODUCER/backend CONSUMER pair whose start times follow collector restoration, on the **existing page before any reload**. The pair must share a trace ID and the backend parent must be the browser span ID. Navigation/reload and a seventh add then verify persistence. Final visible state is **7 added / 7 audited / 6 background increments / done**. All user events survive; this does **not** promise retention of telemetry batches during the outage. Exporter failure logs explicitly show batches may be dropped.

Checks cover trace/span ID shape, PRODUCER→CONSUMER parentage, INTERNAL audit children, `reflex.event.background`, success status, intentional-error ERROR status plus exception event, hashed `session.id`, render spans in dev and production, socket-connect spans and browser-supported web-vital spans. ASGI websocket attributes contain `token=REDACTED`. Offline verification scans **complete collector requests** for every captured raw client token and the synthetic state/input marker; neither appears. Exception messages/stack traces intentionally do appear, as documented.

Full browser frames/messages, pre-outage and post-restore normalized spans, expected/actual assertions and refusal/final screenshots are retained per engine. Dev WebKit's refusal screenshot was visually inspected: inventory remains usable with 5/5/6/done. `SUMMARY.json` is generated from retained evidence; compile roots and available child-stage parentage, service/kind/name counts, ASGI spans, duplicate-handler counts and privacy checks are inspectable there. Web-vital availability differs by browser; no claim is made that every engine emits every vital.

## Historical harness corrections and expected diagnostics

- `alpha2-dev-1`: startup failed because the custom exception handler parameter was named `error`; the public App validator requires `exception`. No browser ran. Fixture correction is retained as `fixture-startup-correction.diff`; original error/clean process results remain. No framework code was changed.
- `alpha2-dev-2` / `alpha2-prod-1`: original 26-check driver passed in both engines, but telemetry recovery was only checked across a reload. `run_case_initial.py` preserves that executable. These are supplementary 104 passing assertions and are not used to establish recovery without reloading.
- `alpha2-dev-3` / `alpha2-prod-2`: strict 29-check driver adds fresh browser/backend export and trace-link checks **before reload**, plus scans raw collector requests for tokens. These are the final recovery matrix.
- Collector refusal produces expected console/request failures, backend batch-export errors and browser-export error reports. WebKit sometimes phrases network refusal as an access-control error; successful CORS exports before/after the outage distinguish this from a broken CORS fixture. Navigation may cancel an in-flight export. The collector logs are therefore not described as error-free.
- WebKit development emits unused modulepreload warnings; production is assessed separately. Bun's React peer warning and uv's neutral-project warning are benign setup noise. The deliberate handler error produces an ERROR span/exception event and a controlled toast.

No new functional issue has been established. No full stable/a1 plugin browser baseline was needed for a passing alpha2 matrix. Hosted observability authentication, long-term storage/querying, gRPC, metrics, sampling configurations, auto-instrumentation CLI mode, other OSes and native Safari are not covered.

## Reproduce from fresh scratch

Use a new scratch root; runners refuse existing app/output directories or occupied reserved ports. These commands use frozen published Python packages, copied app source and task-owned processes. The executed frontend dependency graph is recorded in `environment/frontend-dependency-graph.json.gz`; the replay does not restore that graph as a Bun lockfile. Compatible transitive frontend dependencies may resolve differently on a later clean install. Compare the newly resolved graph with the retained one before treating a rerun as an exact dependency match. This does not change the recorded results:

```sh
DEST=/Users/masen/.codex/worktrees/3564/reflex/prerelease_testing/2026-10-07/tooling_a2/otel
SB=/private/tmp/reflex-otel-replay
mkdir -p "$SB"
cd "$SB"
export UV_CACHE_DIR="$SB/uv-cache"
export UV_PYTHON_INSTALL_DIR="$SB/uv-python"
sh "$DEST/bootstrap.sh" "$SB" "$SB/environment"
uv --no-config venv --python 3.12.14 "$SB/envs/driver"
uv --no-config pip install --python "$SB/envs/driver/bin/python" -r "$DEST/environment/driver.txt"
uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python -m playwright install chromium webkit
for mode in dev prod; do
  NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
    uv --no-config run --no-project --python "$SB/envs/driver/bin/python" python \
    "$DEST/run_case.py" --sb "$SB" --mode "$mode" --out "$SB/results" || exit $?
done
```

Runner starts collector and Reflex via uv from the copied neutral app directory, strips Python import overrides/proxy-bypass variables from server environment, applies import-origin guards for both packages, records full commands, and uses bounded owned-group SIGINT/SIGTERM/SIGKILL cleanup. Collector remains available during final app shutdown to receive final exports. Every browser/context is explicitly closed. Nonzero exit reports startup, assertion or cleanup failure. `summarize.py` can be run via the driver interpreter from neutral scratch to regenerate the retained summary without servers.

## Final retained totals and cleanup

| Run | Chromium / WebKit | OTLP requests | Spans | Status |
| --- | --- | ---: | ---: | --- |
| dev-2 original | 26/26 + 26/26 | 29 | 181 | supplementary, recovery across reload |
| prod-1 original | 26/26 + 26/26 | 30 | 196 | supplementary, recovery across reload |
| dev-3 strict | 29/29 + 29/29 | 34 | 200 | final, recovery before reload |
| prod-2 strict | 29/29 + 29/29 | 36 | 192 | final, recovery before reload |

The final matrix receives **70 actual exports / 392 spans** (301 frontend, 91 backend). All trace/span IDs are valid; compile child links, pre-outage one-span-per-handler counts, synthetic payload omission, raw-token omission and public browser header checks pass. JSON/protobuf and service/name/kind/ASGI detail is retained in SUMMARY. The initial dev-1 fixture startup error has no browser checks or exported spans and is excluded from these totals.

At **2026-10-07 09:17:34 UTC**, `cleanup-final.json` records all 18 owned process groups absent, no listeners on 3586/8586/8588, and no Playwright process rows. Each run independently records pre/post cleanup groups and CLI exit status. Successful app CLIs returned 0; intentional collector SIGTERM returns143 are expected. Ruff essential error checks, formatting, Python AST parsing and shell syntax checks pass. Artifact bytecode is removed; source hashes and executed fixture hashes are retained. No further runtime execution is planned.

Final artifact review also inspected the production Chromium screenshot: 7/7/6/done, preserved synthetic note and usable controls. All four completed runs have identical resolved frontend dependency graphs. Collector logs contain no decode errors or receiver tracebacks. Final artifact size is approximately 1.08 MB; source-only AST checks and retained-number assertions pass.
