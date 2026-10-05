# Runtime exploration

Published `reflex==0.10.0a1` passed these actual browser scenarios in dev,
self-hosted prod, and prod with `frontend_path="/qa"`:

- State increment, subprocess output, intentional failed event followed by a
  successful event, automatic memo components, client and direct route loading.
- `/articles/7?self=1` with a header named `self` hydrates normally.
- Direct dynamic routes return 200; unknown routes and extra path segments return
  404. Gzip asset bodies decompress to exactly the ordinary JavaScript bytes.
- Editing the global CSS asset changes the displayed color without reloading or
  resetting State. No development stylesheet preload link was emitted.
- Reformatting `.web/package.json` to compact JSON retained the real frontend
  installation cache. `dev-json.log` records the cache hit.
- Every output line produced by Reflex in all three completed CLI logs parses as JSON, including
  app stdout/stderr and a descendant process. Intentional event exceptions are
  retained. A separate real worker failure verifies one JSON record with an
  `exception` field, existing JSON passthrough and a late descendant's output.
- SIGTERM without a TTY exits the CLI, backend and frontend descendants. The
  coroutine lifespan cancellation marker appears without the old cancellation
  error. Known test PIDs no longer exist after shutdown.

Evidence: `evidence/{dev,prod,prod-prefix}/browser.json` and screenshots,
`prefix-http.json`, `log-audit.json`, completed `*-json.log`, and
`logging-supervisor.json`. Browser drivers use actual Chromium/Chrome and record
console, page exceptions and every observed HTTP response.

Each combined shell log begins with one non-JSON warning from `uv` about using
`--no-project` outside a project. `log-audit.json` records that exact wrapper
line separately; it is emitted before Reflex starts. Additional non-JSON lines
fail the audit.

`diagnostics-review.json` independently checks the saved browser evidence.
Dev has no console/page/observed-HTTP errors. Ordinary and prefix prod each
have one URL-less console 404, no page errors and no failing observed HTML/JS/
CSS response. The sample omits a favicon; the console record does not identify
its URL, so the reports retain this qualification. See `../REVIEW.md` for the
driver's remaining diagnostic enforcement/evidence-preservation gaps.

The 1,500-State case still fails in the browser. It has valid HTTP responses but
React exhausts its commit stack. See [independent scale comparison](../enterprise/many_states/REPORT.md)
and the central findings. `QA_EXTRA_STATES` creates reproducible dormant State
classes; their generated providers still affect a real page.

## Rerun

Copy this directory into a fresh `/private/tmp` app directory. Use a disposable
venv installed from `../inventory/alpha-requirements.txt`; also install published
Playwright if running the browser driver. Never run from the framework checkout
or install it. Start with `uv --no-config run --no-project --python <venv>/bin/python
reflex run --frontend-port 3142 --backend-port 8142 --json --loglevel debug`.
Prod uses `--env prod --frontend-port 3142 --backend-port 3142`.
`QA_FRONTEND_PATH=/qa` selects the prefix case; `QA_EXTRA_STATES=1500` selects the
scale repro. Set `CI=true`, disable telemetry and remove `PYTHONPATH`.

From the neutral app directory, prefix each command with the same `uv` runner:

```sh
python /absolute/path/to/lifecycle/browser_checks.py --url http://localhost:3142 --css-path /absolute/neutral/app/assets/qa.css --output /private/tmp/dev-evidence
python /absolute/path/to/lifecycle/browser_checks.py --url http://localhost:3142/qa --output /private/tmp/prod-evidence
python /absolute/path/to/lifecycle/http_probe.py --url http://localhost:3142/qa --output /private/tmp/http.json
python /absolute/path/to/lifecycle/logging_probe.py --output /private/tmp/logging.json
```

`QA_CHROME_EXECUTABLE` can select an installed Chrome binary. Otherwise install
Chromium with the same published Playwright version and use its browser.
Save logs, send SIGTERM to the `reflex` worker, wait for exit, then run
`audit_logs.py --root <saved evidence directory>` after collecting all three
named logs. The controlled backend failure is expected; additional error records
fail the audit. CSS is restored in a `finally` block.

Windows socket-handle behavior, unsupported Node preflight and the npm-switch
explanation were not exercised on this macOS/Bun run.
