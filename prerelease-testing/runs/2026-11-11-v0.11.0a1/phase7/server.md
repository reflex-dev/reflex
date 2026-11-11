# Phase 7 re-verification: server / network / redis group (reflex 0.11.0a2)

`OLDSB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad`, work dir `W=$OLDSB/p7/work/net`.
Ports: 3340-3347, 8343; Redis 6391 (own `redis-server --save '' --appendonly no`). One server at a time. All servers, proxies and
Redis were stopped at the end, and the ports were checked free. Evidence: `phase7/server/`: `bin/` (scripts), `src/` (apps), `res/`
(raw outputs, handshake matrices, jsonl), `logs/` (trimmed server logs), `shots/`.

## Venvs and RECORD check

Each venv was checked with `cd /tmp && <venv>/bin/python -I $OLDSB/p7/work/cm/scripts/verify_record.py` before use and again after
all runs. Every check printed OK.

| venv | content | RECORD |
|---|---|---|
| `$OLDSB/p7/envs/new` | reflex 0.11.0a2, reflex-base 0.11.0a2, reflex-components-core 0.11.0a2, python-engineio 4.15.1, granian 2.8.8, redis 8.2.0b1 | OK, before and after |
| `$OLDSB/p7/envs/prev` | reflex 0.10.1, granian 2.8.8, redis 7.4.1 | OK, before and after |
| `$OLDSB/p7/work/cm/envs/ctrl` (a1 control) | reflex 0.11.0a1 train (reflex-base 0.11.0a1), granian 2.8.7; files have link count 1 (not hardlinked) | OK, before and after |
| `$W/envs/drv` (new, built with `--link-mode=copy` and its own `UV_CACHE_DIR`) | python-socketio 5 + aiohttp client driver; no reflex | OK (no reflex dists) |
| `$OLDSB/p7/envs/driver` | playwright | OK (no reflex dists) |

Every app asserts `rx.__file__.startswith($EXPECT_VENV/)`, and runs happen from app dirs under `$W/run/`, never from the checkout.

## Results

| finding | fix PR | a2 result | evidence |
|---|---|---|---|
| FINDING-022 (a): same-origin single-port prod behind a TLS terminator that keeps Host and adds no X-Forwarded-* | #7799 | **PASS** | `bin/cell.sh` (the original `tls_run.sh` setup: `REFLEX_API_URL=https://app.test:T`, `tls_term.py` in front, Chromium clicks inc twice). a2: count=2, 1 websocket open, raw `Host app.test:T` + `Origin https://app.test:T` gives 101. a1 control: count=0, 12 opens, all 403 (reproduces). 0.10.1: count=2. a2 also connects through the `xfp-xfh` and `caddy-behind-edge` (XFP `http`) profiles, and raw `render-wss` (XFP `wss`) gives 101. a1 fails `caddy-behind-edge` and `render-wss`. `res/new_h0.out`, `res/a1_h0.out`, `res/prev_h0.out`, `res/*_hs.txt`, `shots/new_h0_passthrough.png`, `shots/a1_h0_passthrough.png` |
| FINDING-022 (b): doc-literal split deployment, `docs/hosting/self-hosting.md` @ v0.11.0a2 | #7799 | **PASS** | `bin/split.sh`, literally `REFLEX_DEPLOY_URL=http://localhost:3343 reflex run --env prod --backend-only --backend-port 8343` + `REFLEX_API_URL=http://localhost:8343 reflex run --env prod --frontend-only --frontend-port 3343`. a2: count=2. The backend's own origin still opens (101), so `deploy_url` adds an origin instead of replacing one. a1 with the same recipe: count=2, but its own origin gets 403. Old a1 recipe (no `REFLEX_DEPLOY_URL`): fails on a2 and a1 (by design), and a2 now logs the actionable warning. 0.10.1: count=2. `res/{new,a1,prev}_split_*.out` |
| FINDING-022 (c): Host-rewriting proxy with `X-Forwarded-Host` (Azure Front Door profile) | #7799 | **PASS** | Chromium through `hproxy.py afd` (TLS, Host becomes `origin.azurewebsites.test`, XFH and XFP set). hops=0: rejected (count=0, 12 opens), and one warning names `trusted_proxy_hops (REFLEX_TRUSTED_PROXY_HOPS)` (`res/new_h0_afdwarn.out`). hops=1: count=2. hops=2 with single-entry XFH: count=2, raw 101 (leftmost entry of a short chain). a1: connects at the default, through engine.io's unconditional XFH (`res/a1_h0.out`). |
| FINDING-022 (d): a cross-site origin is still rejected; a trusted XFP https rejects an `http://` origin | #7799 | **PASS** | A Chromium page on `http://evil.test:E` opens raw `WebSocket`s to the app (via the TLS front door and directly): ERROR on a2 at hops 0/1/2, on a2 split + deploy_url, and on a1. Both OPEN on 0.10.1 (`res/*_xsite.json`). Raw handshakes on a2: cross-site, `null`, userinfo and suffix origins all give 403 at every hops value. `Origin http://H` + XFP `https`/`wss` gives 403 at hops 1 and 2 and 101 at hops 0, where XFP is untrusted. In the browser (`bin/xfplie.sh`, page over plain http through a proxy that claims XFP https): hops=1 count=0 with 403, hops=0 count=2, and a proxy without XFP connects at both. `res/new_xfplie_h*.out` |
| FINDING-022 (e): the warning never suggests `REFLEX_DEPLOY_URL=<rejected origin>` | #7799 | **PASS** | Every a2 rejection warning (7 logs, 8 warnings, including attacker origins) contains 0 `REFLEX_DEPLOY_URL=` and 0 `CORS_ALLOWED_ORIGINS=` value strings. The wording is always "set REFLEX_DEPLOY_URL on the backend to the frontend's public URL". With `GRANIAN_WORKERS=2` + Redis, 30 rejected handshakes produce exactly 2 warnings, one per worker (`logs/smoke.log`). |
| FINDING-023: CORS rejection reported as "server unreachable" | #7799 (backend part) | **PASS** (backend); frontend unchanged by design | The a2 backend logs `Warning: Rejected an event websocket from origin '...': ... (request Host ..., X-Forwarded-Host ... ignored as trusted_proxy_hops is 0); <fix>. This warning is logged once per worker.` a1 logs only engine.io's line. The toast is identical on a1 and a2 by design: "Cannot connect to server: websocket error. Check if server is reachable at ws://localhost:8343/_event" (`res/*.json` `body_tail`). Unchanged and known: engine.io's own "`<origin> is not an accepted origin.`" line still follows the Reflex warning. |
| FINDING-024: `rx.App()()` no longer returns a Starlette app | #7816 | **PASS** | `git show v0.11.0a2:CHANGELOG.md`: the first Breaking Changes entry of v0.11.0a2 reads "Calling an `rx.App` instance (`app()`) returns a plain ASGI callable instead of a `Starlette` app, so the result no longer has `add_middleware`, `routes` or `mount`. Add Starlette middleware and routes with `api_transformer` instead. (#7624)". The `docs/api-routes/overview.md` target exists at the tag. (#7799 has no a2 entry of its own: it was folded into the a1 #7641 breaking entry, which now says deploy_url is allowed "in addition to the backend's own" and mentions `trusted_proxy_hops`.) |
| FINDING-030: forked workers share one StateManagerRedis id; oplock waiters passed over ~1 s | #7795 | **PASS** | `bin/oplock.sh` (prod, Redis, `REFLEX_OPLOCK_ENABLED=true`, fork, 1 client, 300 pipelined events + 100 `/api/bump`, 6 runs per cell; stall = api wait > 500 ms). Worker-id probe: a2 has 4 pids and 4 state-manager ids (w4), 2 and 2 (w2). a1 has 4 pids and 1 id, 2 and 1; 0.10.1 has 2 and 1. Stalls: **a2 0/24** (worst api_max 174 ms). **a1 17/24** (1012-3023 ms: w2 conc2 5/6 at ~1.0 s, conc4 6/6, w4 conc4 6/6 at 1-3 s). 0.10.1 w2: 11/12 at ~5.0 s. Final counts exact in 54/54 runs. `res/oplock.jsonl`, `res/op-*.iid.txt`, summarized with `bin/opsumm.py` |
| FINDING-033: kill -9 of one granian worker stops the whole prod server | #7803 | **PASS** | `bin/kill9.sh` (prod, Redis, 2 workers, kill -9 the socket's worker mid-event). a2 default: `/ping` returned 2xx in all 40 polls over 10 s after the kill. Pids went from [28887 28889] to [28889 28943]. 4 fresh socket clients 4/4 ok, one served by the respawned pid. With `GRANIAN_LOG_LEVEL=info`: `[ERROR] Unexpected exit from worker-1 / [INFO] Respawning worker-1 / Spawning worker-1 with PID: 28943 / Started worker-1`. `GRANIAN_RESPAWN_FAILED_WORKERS=false` and `=off`: the server stops at once ("Reflex app stopped."), the old behavior. a1 control at the default: it stops (reproduces). `=maybe`: rc=1, `EnvironmentVarValueError: GRANIAN_RESPAWN_FAILED_WORKERS: 'maybe' is not a valid boolean. Recognized values: , 0, 1, f, false, n, no, off, on, t, true, y, yes`. That is clear, but it arrives as a raw traceback after the full compile and build (see observation 2). `res/kill9_*.out`, `logs/k9-*.log` |
| FINDING-031: Redis outage > ~5 s drops cross-worker updates (not fixed this train, #7835) | — | **still reproduces** (expected) | `faults.py redis_restart --down 10`, a2, 2 workers: after restart, 4 of 10 `/api/bump` deltas reach the connected socket (the 6 that landed on the other worker are lost). Log: `_subscribe_socket_record_updates: task exceeded exception limit 5 within 60.0s`. `res/f031.jsonl`, `logs/f031-new.log` |
| FINDING-032: a dead worker's socket record gives the returning tab a new token (not fixed this train) | — | **still reproduces** (expected) | `kill9.sh` a2 default, same-token resume after the respawn: connects in 0.009 s but receives `new_token`, and count restarts at 1. `res/kill9_new_default.out` |
| General smoke: blank template, prod single-port, `GRANIAN_WORKERS=2` + Redis, event + background task, reload | all | **PASS** | `reflex init --template blank`, page replaced by `src/smoke_page/smoke.py`. `drive_app.py --all-console` 2× in fresh browsers: inc ×2 gives count=2, bg task running, then bg=5, then idle. Reload keeps count=2/bg=5, a further inc gives 3. Events were served by both worker pids across runs. Server log: no warning or error before the deliberate rejection probe. Console: only `Disconnect websocket on page navigation` (log level). 0 page errors, 0 failed requests, no 4xx/5xx. `res/smoke_run{1,2}.json`, `shots/smoke_end.png`, `logs/smoke.log` |

## NEW-ISSUE

1. **(LOW, diagnostics) The rejection warning does not name a trusted `X-Forwarded-Proto` when it caused the rejection.**
   The behavior is correct (asymmetric scheme rule), but the advice points at Host forwarding, which is not the cause.
   - Repro: `bin/xfplie.sh new 1` runs `reflex run --env prod` on 3340 with `REFLEX_TRUSTED_PROXY_HOPS=1` and
     `REFLEX_API_URL=http://app.test:3341`, behind `hproxy.py 3341 3340 xfp-https`, a plain-http proxy that keeps Host and sets
     `X-Forwarded-Proto: https`. Open `http://app.test:3341/` in Chromium.
   - Result: 403 forever. The log reads: `Rejected an event websocket from origin 'http://app.test:3341': in prod mode the backend
     accepts only its own origin (request Host 'app.test:3341', X-Forwarded-Host None trusted); if it is your frontend's origin, set
     REFLEX_DEPLOY_URL ... or add it to cors_allowed_origins; a reverse proxy must forward the original Host header.`
   - The origin matches Host exactly. The real reason is that the trusted proxy reports https while the page is http (a
     misconfigured proxy, or an http page behind an https-claiming hop). The warning never mentions `X-Forwarded-Proto`.
   - Suggested: include the trusted XFP value in "what the backend saw", and add a hint when only the scheme differs. Not
     release-blocking.

## Observations (not filed)

1. **By design, recorded for reviewers:**
   - With `trusted_proxy_hops >= 1`, a non-browser client that sends `X-Forwarded-Host: evil.example` with
     `Origin https://evil.example` directly to the backend gets 101. A browser cannot set XFH on a handshake, so this is the
     documented trust model.
   - With hops=2 and a two-entry XFH `edge.test, app.test:T`, the backend reads `edge.test` (entry 2 from the right), so the
     app's own origin gets 403 and `evil.example, app.test:T` lets `evil.example` in. This matches the `_trusted_forwarded_value`
     docstring.
   - At hops=0, `Origin http://H` with `X-Forwarded-Proto: https` gets 101, because XFP is untrusted. That matches 0.10.1 and is
     the documented behavior.
2. **`GRANIAN_RESPAWN_FAILED_WORKERS` is validated late.** An invalid value is reported only after the whole compile and
   production build and the "App running at" banner, as a ~30-line traceback, though the last line is clear and names the
   variable (rc=1). For comparison, `GRANIAN_WORKERS=abc` on a2 gives a bare `ValueError: invalid literal for int()` (pre-existing),
   so the new variable is the better-behaved of the two. A pre-flight check with a one-line error would be nicer.
3. **The a2 `CHANGELOG.md` section has no #7799 entry.** The same-origin-behind-TLS fix and the new direct `python-engineio
   >=4.12.0,<5.0` dependency appear only in the edited a1 #7641 breaking entry, which now links #7799. That is fine for the
   collapsed 0.11.0 final changelog, but an a1 tester reading only the a2 section would not see it.
4. **engine.io's own rejection line remains.** Every Reflex warning is followed by engine.io's `<origin> is not an accepted
   origin. (further occurrences of this error will be logged with level INFO)`. This is known and listed as not addressed in
   #7799.
5. **Harness note (not a product issue).** In an interactive tool shell with job control, `setsid cmd & pid=$!` forks, so `$!`
   is the wrong pid and the proxy leaks. One ad-hoc run was invalidated this way and redone as a script (`bin/xfplie.sh`).
   The scripted runs (`cell.sh`, `warn.sh`, `split.sh`) are unaffected: each profile produced a distinct, expected result.

## Rerun

```
. phase7/server/bin/lib.sh   # (copy bin/ and src/ to $W first; lib.sh hardcodes W=$OLDSB/p7/work/net)
bin/cell.sh new new_h0 3340 3341 ; bin/cell.sh new new_h1 3340 3341 REFLEX_TRUSTED_PROXY_HOPS=1 ; bin/cell.sh new new_h2 3340 3341 REFLEX_TRUSTED_PROXY_HOPS=2
bin/cell.sh a1 a1_h0 3340 3341 ; bin/cell.sh prev prev_h0 3340 3341
bin/warn.sh new new_h0_afdwarn 3340 3341 afd
bin/split.sh new new_split_doc 3343 8343 REFLEX_DEPLOY_URL=http://localhost:3343 ; bin/split.sh new new_split_nodeploy 3343 8343
bin/xfplie.sh new 1 ; bin/xfplie.sh new 0
bin/oplock.sh <new|a1|prev> <2|4> res/oplock.jsonl "2 4" 6 ; envs/drv/bin/python -I bin/opsumm.py res/oplock.jsonl
bin/kill9.sh new 2 res/kill9.jsonl new-default GRANIAN_LOG_LEVEL=info ; bin/kill9.sh new 2 res/kill9.jsonl new-false GRANIAN_RESPAWN_FAILED_WORKERS=false ; bin/kill9.sh a1 2 res/kill9.jsonl a1-default
```
