# client_error cluster — Reflex 0.9.9a1 pre-release testing

Feature under test: **PR #6827** "surface unprocessable state deltas as fatal client errors".
When the frontend receives a state delta it cannot dispatch (a substate with no
dispatch function — i.e. the frontend and backend disagree about the state tree),
the frontend validates the whole delta first, logs an actionable browser-console
error, reports it to the backend over a new `client_error` socket event, and marks
the session **fatal** (stops sending events / drops incoming updates until reload).
The backend `EventNamespace.on_client_error` handler logs an actionable terminal
message, and is hardened against abuse (non-dict payloads ignored, values
sanitized + truncated, unknown sids gated, per-sid + per-window rate limits).

Tested against `reflex==0.9.9a1` + alpha subpackages from PyPI (shared venv
`$SB/envs/smoke`). No baseline-vs-0.9.8 comparison applies: the whole feature is
new in 0.9.9a1, so there is nothing in 0.9.8 to regress against.

## Environment / ports
- App dir: `$SB/apps/client_error/` (this dir). App module: `client_error/client_error.py`.
- Ports: frontend **3220**, backend **8220** (from the reserved range).
- Driver venvs: `$SB/envs/driver` (playwright) and `$SB/envs/client_error_drv`
  (python-socketio, for raw socket abuse). Chromium at `/opt/pw-browsers/chromium`.
- Always run reflex from the app dir with `REFLEX_TELEMETRY_ENABLED=false` and
  `NO_PROXY=localhost,127.0.0.1,::1`.

## Key operational notes (for re-runners)
- **Background reflex processes do survive across shells here** once the app is
  cleanly built, but a **broken `.web` build makes the granian worker crash**
  ("Unexpected exit from worker-1"). My first `reflex init`+run got its bun
  install stuck for ~15 min while another agent installed concurrently; killing
  it left `.web/` half-initialized (no `app/root.jsx`), so the vite dev server
  later died with *"Could not find a root route module ... app/root.tsx"*.
  Fix: `rm -rf .web .states` and re-run `reflex run` — clean build came up in ~8s.
- **bun/registry flakiness (env, not reflex):** `registry.npmjs.org` is in the
  proxy `no_proxy`, so bun fetches it directly; that direct route was slow/flaky
  (18s, `ConnectionClosed` on parallel manifest fetches). A retry loop with
  registry kept in `no_proxy` eventually succeeded ("159 packages installed").
- `--frontend-only` rejects `--backend-port`; to point a stale frontend at a
  chosen backend, set `api_url` in `rxconfig.py` (env.json is regenerated from
  config on every frontend serve, ignoring manual edits and the `API_URL` env var).
- **`pkill -f "backend-only --backend-port 8220"` self-terminates the tool shell**
  (the pattern matches the running command line). Kill reflex by explicit PID.

## What I tested (scripts in this dir)

`client_error.py` — app with `State` (counter/log), a normal `bump`, a `chain_bump`
(event chain), `send_unprocessable_delta` (event handler that emits a delta for a
ghost substate — the canonical synthetic mismatch, identical to what the official
integration test `tests/integration/tests_playwright/test_client_error.py` uses),
and `bg_then_break` (a `@rx.event(background=True)` variant).

`drive.py <url> <out> <scenario>` — Playwright driver (scenarios: normal / break /
bgbreak). Captures console, page errors, failed requests, screenshots.
`drive_bg.py` — focused bgbreak observer (polls up to 10s for the mismatch).
`abuse.py` / `abuse2.py` — raw python-socketio abuse of the `client_error` event
(namespace `/_event`, `socketio_path="_event"`). `/tmp/drive_stale.py` and
`/tmp/drive_extra.py` (copied into `artifacts/`) drive the genuine stale-frontend
scenarios.

### Browser tests (real compiled frontend, dev mode)
1. **normal** — bump/bump/chain-bump → counter 1→4, **no** client_error, clean
   backend log, 0 page errors, 0 failed requests. PASS.
2. **break** (event handler emits ghost substate delta) — browser console shows
   the actionable error (`Cannot process state update: no dispatch function for
   substate(s) "reflex___state____state____ghost_state" ... rebuild the frontend
   and check that api_url is correct`); backend terminal logs
   `[Reflex Frontend Exception] [SID: ...] State update failed: no dispatch
   function ... frontend/backend state mismatch. Rebuild the frontend or check
   that api_url ...`. Session is **fatal**: subsequent bumps do nothing
   (counter stays 1), `performance...navigation.type == "navigate"` (no
   auto-reload), 0 uncaught page errors. PASS.
3. **bgbreak** (background task emits the ghost delta) — same client_error path;
   with an adequate observation window the mismatch console error fires at
   ~0.36s and the fatal flag then blocks the next bump (counter stays 2). PASS.
   (One earlier back-to-back run showed a timing race where the bg-emitted delta
   arrived >2s late so a later bump slipped through first — a test-load timing
   artifact, not a framework defect; recorded as an anomaly.)

### Genuine real-world mismatch (stale frontend vs changed backend)
Built the frontend for `State`, then **added a brand-new substate `class Extra`**
that `bump` also mutates, and restarted **backend-only** with `REFLEX_SKIP_COMPILE=1`
so the served frontend build stays stale (confirmed: no `extra_val` in `.web/app`).
On hydration the backend pushes a delta including the unknown substate; the stale
frontend reports it. Browser console:
`Cannot process state update: no dispatch function for substate(s)
"reflex___state____state.client_error___client_error____state",
"reflex___state____state.client_error___client_error____extra" ... rebuild the
frontend and check that api_url is correct`. Backend terminal logs the matching
`[Reflex Frontend Exception] ... State update failed ... frontend/backend state
mismatch`. Fatal (token never populates, session stops). PASS.
- Note: simply **renaming** the `State` class did **not** by itself produce a
  client_error on load — the base `rx.State` router still hydrates (token
  populated) and a default-valued renamed substate emits no hydration delta, so
  nothing gets dispatched for the unknown key. The mismatch only surfaces once
  the diverged substate actually sends a delta (an added substate that changes on
  hydration, or an event that mutates it). Worth knowing: a renamed/removed state
  is only *reported* when that substate pushes an update, not merely by existing.

### Backend handler robustness (raw socket.io, `abuse.py`/`abuse2.py`)
- **Sanitization works (byte-verified).** A payload with ANSI (`\x1b[31m`),
  newlines (`\n`, `\r\n`), NUL/BEL/BS, and rich markup `[bold red]...[/bold red]`
  is logged with the ESC replaced by a space (`[31m` shows as literal text, no
  color), markup backslash-escaped (`\[bold red]`), and **zero** raw
  ESC/NUL/BEL/BS bytes anywhere in the log file. The only `\n` in the file is
  rich's display-wrapping of one logical log line, which cannot forge a new log
  record (no injected `[SID:]`/level prefix on a fresh logical line). PASS.
- **Truncation works.** A 600-char message is logged as `...CCCCC... (truncated)`
  (500-char bound). PASS.
- **Oversized payload bounded at transport.** A 10 MB `message` **disconnects the
  socket** (engine.io `max_http_buffer_size` = 1 MB, `POLLING_MAX_HTTP_BUFFER_SIZE
  = 1000*1000`) and never reaches the handler/log. PASS.
- **Rate limiting works.** Per-SID cap = 5 (8 sent → 5 logged); per-window cap =
  20 across all sids (verified across 4 reconnecting sids + the 3 earlier
  entries; the 20th trips `Warning: Received more than 20 client_error reports in
  60s; suppressing further reports for this window.`). PASS.
- **Unknown-sid gating works.** A socket that connects **without** a token
  (`Warning: No token provided ...`) produces **no** error-level entry from a
  valid dict payload — gated to debug. PASS.
- **Non-dict payloads (str / list / int) ignored** — no error entry, no crash. PASS.

## FINDING — no-arg `client_error` emit raises an unhandled `TypeError`, bypassing all hardening

`EventNamespace.on_client_error(self, sid, data)` has **no default for `data`**.
python-socketio invokes event handlers as `handler(sid, *data[1:])`; when a client
emits the `client_error` event **with no data argument** (or `None`), the handler
is called with only `sid`, raising
`TypeError: EventNamespace.on_client_error() missing 1 required positional
argument: 'data'`. This is raised **inside socketio before the handler body runs**,
so it **bypasses every guard added by #6827**: the `isinstance(data, dict)` check,
the unknown-sid gate, and both rate limiters.

Verified:
- 31 no-arg emits from one linked socket → **31 tracebacks** logged
  (`abuse2.py`, `backend_only2.log`, 62 matched message lines; rate limiter never
  engaged).
- 5 no-arg emits from an **unlinked (no-token) socket** → **5 tracebacks**, and
  the "Ignoring client_error report from unknown SID" guard fired **0 times**
  (`/tmp/noarg_unlinked.py`, `be_extra.log`) — so it needs **no valid token**.
- Surfaces as an asyncio `Task exception was never retrieved` traceback (printed
  outside the reflex logger), so it is visible even at the default `info`
  loglevel and cannot be suppressed via `--loglevel`.

Impact: unauthenticated backend-log spam / unhandled exception on the hot socket
path — a straightforward DoS-of-logs that defeats the anti-abuse hardening that is
a headline of #6827. Not a crash/RCE (the server keeps running and processed all
subsequent events in every test). Severity: **medium**.
Suggested fix (for maintainers, not applied): give `data` a default
(`data: Any = None`) so the existing `isinstance(data, dict)` guard handles the
missing/None case, or register the handler defensively.

Repro:
```
cd $SB/apps/client_error
REFLEX_TELEMETRY_ENABLED=false NO_PROXY=localhost,127.0.0.1,::1 \
  $SB/envs/smoke/bin/reflex run --backend-only --backend-port 8220 --loglevel info > be.log 2>&1 &
# wait for :8220/ping == 200, then:
$SB/envs/client_error_drv/bin/python /tmp/noarg_unlinked.py     # unlinked, no token
$SB/envs/client_error_drv/bin/python abuse2.py http://localhost:8220 /_event
grep -c "missing 1 required positional argument" be.log         # 2x the emit count
```

## ANOMALY — transient `ERR_CONNECTION_REFUSED` on the event socket (dev mode, benign)
Every dev-mode browser session logged 1–9 console errors like
`WebSocket connection to 'ws://localhost:8220/_event/?token=...&EIO=4&transport=websocket'
failed: ... net::ERR_CONNECTION_REFUSED`, yet the socket then connected and events
worked (counter updated). Appears to be socket.io reconnection churn racing with
backend readiness / vite HMR. Benign (functionality unaffected) but shows up as a
red console error on otherwise-healthy sessions. No backend worker restarts were
found in the log to explain it.

## Artifacts (in ./artifacts/)
- `normal_*`, `break_*`, `bgbreak_*` — console/pageerror/failedreq logs + screenshots.
- `stale_extra.png`, `stale_extra_console.log`, `drive_stale.py`, `drive_extra.py` — genuine mismatch.
- `evidence_escaping_ratelimit.txt`, `evidence_noarg_typeerror.txt`, `evidence_genuine_mismatch.txt`.
- Server logs: `backend_only.log`, `backend_only2.log`, `be_extra.log`, `run_dev.log`.
```
