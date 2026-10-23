# Cluster `schema-mismatch` — reflex 0.10.1a1 (2026-10-23)

State-schema hash / version-mismatch reload + banner (#7553), `window.onerror` without an
`Error` object (#7544), reconnect backoff when the connection closes before connecting (#7605).

Everything ran from PyPI installs: `$SB/envs/shared` (reflex 0.10.1a1, Python 3.11) and
`$SB/envs/prev` (reflex 0.10.0) with `SB=/tmp/claude-0/-home-user-reflex/7eb9e30f-e96c-5de5-9b0e-4a12be91e0f3/scratchpad/prt`.
Browser driver: `$SB/envs/driver/bin/python` (Playwright + Chromium `/opt/pw-browsers/chromium`, `websockets`).
Ports used: frontend 3221 (new prod), 3222 (0.10.0 prod), 3223 (new dev); backend 8221/8222/8223.

## Layout

- `schemaapp/` — the test app (0.10.1a1). `SCHEMA_VARIANT` env var picks a backend-only
  change to the state tree: `""` baseline, `body` (handler body only), `backend` (backend-only var),
  `var` (new frontend var on substate `Sub`), `handler` (new handler), `rename` (renamed handler).
  `rxconfig.py` pins `api_url` from `SCHEMA_API_URL` (default `http://localhost:8221`) so a static
  prod frontend can be served separately from the backend. Pages: `/` (counter, foreach, cond,
  substate, input), `/about` (`rx.ComponentState` tile), `/errors` (buttons that raise frontend
  errors via `rx.call_script`). `rx.App(frontend_exception_handler=...)` appends every received
  frontend exception to `logs/frontend_exceptions.log`.
- `schemaapp_prev/` — same source, built/run with 0.10.0 (`SCHEMA_API_URL=http://localhost:8222`).
- `schemaapp_dev/` — same source, used for dev-mode runs.
- `scripts/` — Playwright drivers (`pwlib.py` captures console, page errors, failed/4xx+ requests,
  websocket frames, loads), `closing_proxy.py` (fake backend that completes the Engine.IO handshake
  then closes on the socket.io CONNECT packet), `kill_port.sh`, `schema_hash.py`.
- `logs/*.json` — per-run captures (`results` key holds the assertions); `*/logs/*.log` server logs;
  `*/shots/*.png` screenshots.

## How to rerun

```bash
SB=/tmp/claude-0/-home-user-reflex/7eb9e30f-e96c-5de5-9b0e-4a12be91e0f3/scratchpad/prt
export REFLEX_TELEMETRY_ENABLED=false
PW="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python"
cd schemaapp

# 1. prod frontend (baseline schema), served statically on 3221 (first run installs bun deps, 1-3 min)
$SB/envs/shared/bin/reflex run --env prod --frontend-only --frontend-port 3221 --loglevel debug > logs/fe_prod_baseline.log 2>&1 &
grep 'export const stateSchema' .web/utils/context.jsx          # d29adae5a051f36dafa3d2ce3c5e3601

# 2. matching backend -> no mismatch
$SB/envs/shared/bin/reflex run --env prod --backend-only --backend-port 8221 --loglevel debug > logs/be_prod_baseline.log 2>&1 &
(cd ../scripts && $PW t_mismatch.py http://localhost:3221/ ../logs/match_baseline.json ../schemaapp/shots/match_baseline --expect match)
../scripts/kill_port.sh 8221

# 3. backend with a changed state tree -> reload once, then banner; after the cooldown reload again
SCHEMA_VARIANT=var $SB/envs/shared/bin/reflex run --env prod --backend-only --backend-port 8221 --loglevel debug > logs/be_prod_variant_var.log 2>&1 &
(cd ../scripts && $PW t_mismatch.py http://localhost:3221/ ../logs/mismatch_var.json ../schemaapp/shots/mismatch_var --expect mismatch --cooldown-wait 11)
../scripts/kill_port.sh 8221
REFLEX_AUTO_RELOAD_COOLDOWN=3s SCHEMA_VARIANT=var $SB/envs/shared/bin/reflex run --env prod --backend-only --backend-port 8221 > logs/be_cd3.log 2>&1 &
(cd ../scripts && $PW t_mismatch.py http://localhost:3221/ ../logs/mismatch_cd3.json ../schemaapp/shots/cd3 --expect mismatch --cooldown-wait 4)
../scripts/kill_port.sh 8221

# 4. hash stability: rebuild the frontend with a handler-body-only change -> same stateSchema
../scripts/kill_port.sh 3221
SCHEMA_VARIANT=body $SB/envs/shared/bin/reflex run --env prod --frontend-only --frontend-port 3221 > logs/fe_prod_variant_body.log 2>&1 &
grep 'export const stateSchema' .web/utils/context.jsx          # still d29adae5...

# 5. frontend error reporting (matching backend on 8221)
$SB/envs/shared/bin/reflex run --env prod --backend-only --backend-port 8221 --loglevel debug > logs/be_prod_baseline_errors.log 2>&1 &
(cd ../scripts && $PW t_errors.py http://localhost:3221/errors ../schemaapp/logs/frontend_exceptions.log ../logs/errors_prod_new.json ../schemaapp/shots/errors_prod_new)
../scripts/kill_port.sh 8221

# 6. backoff with the backend down, then recovery (60 s window)
(cd ../scripts && $PW t_backoff.py http://localhost:3221/ ../logs/backoff_down_new.json ../schemaapp/shots/backoff_down_new 60 \
   --start-backend "REFLEX_TELEMETRY_ENABLED=false $SB/envs/shared/bin/reflex run --env prod --backend-only --backend-port 8221" --backend-cwd $PWD)
../scripts/kill_port.sh 8221

# 7. backoff when the server closes the transport on the CONNECT packet (proxy frame limit)
$SB/envs/driver/bin/python ../scripts/closing_proxy.py 8221 ../logs/closing_proxy_8221.log &
(cd ../scripts && $PW t_backoff.py http://localhost:3221/ ../logs/backoff_proxyclose_new.json ../schemaapp/shots/backoff_proxyclose_new 30)
kill %1   # the proxy

# 8. dev mode (schemaapp_dev): hot reload after adding a var, and a dev-only mismatch warning
cd ../schemaapp_dev
SCHEMA_API_URL=http://localhost:8223 $SB/envs/shared/bin/reflex run --frontend-port 3223 --backend-port 8223 --loglevel debug > logs/dev_hotreload.log 2>&1 &
(cd ../scripts && $PW t_dev_hotreload.py http://localhost:3223/ ../schemaapp_dev/schemaapp/schemaapp.py ../logs/dev_hotreload.json ../schemaapp_dev/shots/dev_hotreload)
../scripts/kill_port.sh 3223 8223
SCHEMA_VARIANT=var SCHEMA_API_URL=http://localhost:8223 $SB/envs/shared/bin/reflex run --backend-only --backend-port 8223 > logs/dev_be.log 2>&1 &
SCHEMA_API_URL=http://localhost:8223 $SB/envs/shared/bin/reflex run --frontend-only --frontend-port 3223 > logs/dev_fe.log 2>&1 &
(cd ../scripts && $PW t_mismatch.py http://localhost:3223/ ../logs/mismatch_dev_var.json ../schemaapp_dev/shots/mismatch_dev_var --expect devwarn)
../scripts/kill_port.sh 3223 8223

# 0.10.0 baseline: same commands in schemaapp_prev with $SB/envs/prev, ports 3222/8222 and
# SCHEMA_API_URL=http://localhost:8222 (steps 2, 5, 6, 7).
```

## Results

| check | 0.10.1a1 | 0.10.0 |
|---|---|---|
| CONNECT auth carries `state_schema` | yes (`40/_event,{"event":{...},"state_schema":"d29adae5..."}`) | no key (expected) |
| compiled `.web/utils/context.jsx` exports `stateSchema` | yes, prod and dev | absent |
| matching backend | no `state_mismatch`, 1 load, no banner | n/a |
| backend `SCHEMA_VARIANT=var` / `handler` | `state_mismatch` frame `{"backend":"bf1aee..","reload_cooldown_ms":10000}`, exactly one auto reload (2 `load` events), then banner "A new version of this app is available. [Reload]"; app keeps working under banner (increment -> count: 1); banner button reloads and (still inside cooldown) banner again; after 11 s a navigation auto-reloads again. Backend logs `Warning: Frontend state schema ... does not match the backend state schema ...` | n/a |
| `REFLEX_AUTO_RELOAD_COOLDOWN=3s` | `reload_cooldown_ms: 3000`; after a 4 s wait the next navigation auto-reloads again | n/a |
| deprecated `REFLEX_AUTO_RELOAD_COOLDOWN_TIME_MS=2000` | `reload_cooldown_ms: 2000` + DeprecationWarning in the backend log | n/a |
| hash stability (`body` and `backend` variants) | `stateSchema` unchanged (`d29adae5...`) after a full rebuild with the handler body changed; python-side hashes equal for baseline/body/backend and differ for var/handler/rename | n/a |
| dev: `reflex run`, then add a var to `Sub` | var renders after ~1 s via HMR, no reload, no banner, exactly one `state_mismatch` + console warning per backend restart (edit and revert), count keeps working | n/a |
| dev: fe-only baseline vs be-only `var` | `state_mismatch` received, console warning only, 1 load, no banner (but the warning is printed twice, see anomalies) | n/a |
| `/errors`: `throw 'plain string'` | reported (`undefined: undefined\nundefined`), no secondary error | same text |
| `/errors`: `new ErrorEvent('error', {})` | reported (`"\n    at :0:0"`), console clean | TypeError `Cannot read properties of undefined (reading 'name')` thrown inside `window.onerror`, the TypeError is what gets reported |
| `/errors`: ErrorEvent with only a message | reported with the message, console clean | TypeError as above |
| `/errors`: real ResizeObserver loop | 49 reports `ResizeObserver loop completed with undelivered notifications.\n    at http://localhost:3221/errors/:0:0`, console clean | 49 page errors `Cannot read properties of null (reading 'name')`, nothing reported |
| `/errors`: `throw new Error`, `Promise.reject` | reported with stack | same |
| backend down, 60 s | 23 websocket attempts, gaps 0.2 s -> ~2 s plus socket.io's own jitter (up to ~6 s); toast "Cannot connect to server: websocket error." ; recovery after backend start 1.3 s / 2.4 s (one run 23.9 s while another test ran in parallel) and toast dismissed | 23 attempts, same pattern, recovery 3.6 s |
| server closes transport on CONNECT, 30 s | 20 attempts, backoff 0.2 s -> 2 s cap, toast "Cannot connect to server: connection closed before connecting (transport close)." | **2287 attempts in 30 s (~75/s tight loop), no toast** — #7605 fixes this |

## Anomalies / observations (none blocking)

1. **Banner covers the top of the page.** `#reflex-new-version-banner` is `position:fixed;top:0` with
   max z-index and no body offset, so the app's own top row (here the nav links `home about errors`)
   sits under it and is not clickable until the user reloads. See `schemaapp/shots/mismatch_var_1_after_load.png`.
   New in 0.10.1a1 (banner is new); low.
2. **Dev mode logs the mismatch warning twice per `state_mismatch` frame** (`logs/mismatch_dev_var.json`:
   1 frame, 2 identical `console.warning`s; the hot-reload run shows the same 1:2 ratio). Prod is 1:1.
   Probably the React StrictMode double effect registering two listeners. Cosmetic; low.
3. **ResizeObserver loop notifications are reported one event per observer iteration**: a tight RO loop
   produced 49 `handle_frontend_exception` events in ~1 s (`schemaapp/logs/frontend_exceptions.log`).
   Behaviour matches the #7544 intent (report instead of throwing), but there is no de-duplication or
   throttling, so a page with a persistent RO loop will spam the backend. 0.10.0 threw 49 TypeErrors in
   the console instead. Low/medium depending on how common RO loops are in user apps.
4. `throw 'plain string'` (a non-Error primitive) is reported as `undefined: undefined\nundefined`
   because the handler reads `.name/.message/.stack` of the string; the `msg` argument
   (`Uncaught plain string`) is dropped. Same in 0.10.0; low.
5. Prod static server answers `/about` with `307 -> /about/` (Starlette StaticFiles directory redirect);
   same in 0.10.0. Benign.
6. `favicon.ico` 404 in every run: the test app has no `assets/` dir. Benign.
7. 0.10.0 only: with no `schemaapp/__init__.py`, `reflex run --env prod --backend-only` named the
   states `schemaapp____state` while the compiled frontend used `schemaapp___schemaapp____state`
   ("no dispatch function for substate" console error, events dead). 0.10.1a1 worked in the same
   layout (the first baseline run was done before `__init__.py` was added). Not a regression; noted
   because it is exactly the class of skew the new hash is meant to catch (and 0.10.1a1 would).
8. Backend-down recovery took 23.9 s in one run (`logs/backoff_down_new.json`) vs 1.3 s / 2.4 s in two
   other runs; that run overlapped with the 0.10.0 run starting its own backend. Most likely the
   combined socket.io reconnection delay (up to ~6 s observed) plus a slow backend start; not
   reproduced in isolation.
9. The `--loglevel debug` prod backend log prints the full `Config(...)` repr including `api_url`; fine.
