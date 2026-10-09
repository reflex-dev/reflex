# Item `a5_hydration_router` — reflex#7360 (router data / credential headers) regression hunt + hydration re-runs on 0.10.0a5

Date 2026-10-08. Under test: **reflex 0.10.0a5 / reflex-base 0.10.0a5** (PyPI), shared read-only venv `$SB/envs/a5`.
Comparisons (same machine, back to back, one server at a time): `$SB/envs/a4` (0.10.0a4, the leaking positive control for
#7360), `$SB/envs/alpha` (0.10.0a1, F-002/F-003 positive control), `$SB/envs/a3` (0.10.0a3, A3-11/A3-12 positive control),
`$SB/envs/stable` / `a3_hydration-tp-s912` (0.9.12). Browser: Playwright + `/opt/pw-browsers/chromium` from `$SB/envs/driver`.
Nothing installed from / run inside a checkout: apps run from `$W/run/<name>` and assert `reflex.__file__` is under
`/scratchpad/envs/$RVH_VENV/` (set by `scripts/srv.sh`); drivers assert `/envs/driver/`.
Ports: 3140-3159 / 8140-8159 (redis 8149).

```bash
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a5_hydration_router
NP="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1"; DRV=$SB/envs/driver/bin/python
# To rerun elsewhere (the scripts hard-code W): mkdir -p $W/{run,logs,results}; cp -r src drivers scripts cv $W/
# Third-party venv (PyPI only, cwd=$SB):
cd $SB && uv --no-config venv --python 3.12 $SB/envs/a5_hydration_router-tp-a5 && uv --no-config pip install \
  --python $SB/envs/a5_hydration_router-tp-a5/bin/python --prerelease=allow 'reflex[db]==0.10.0a5' 'reflex-base==0.10.0a5' \
  'reflex-local-auth==0.5.0' 'reflex-google-auth==0.2.0' 'google-api-python-client>=2.184.0' 'pydantic<2.14'
```
(Speed-up used: run dirs were seeded with `cp -a` of the a4 pass's built `.web` dirs to reuse `node_modules`; reflex
re-initialises `.web` on a version change.)

## Part 1 — reflex#7360 regression hunt (a5 vs a4, back to back)

Read first: PR #7360 description + all review threads (cookie-only filter extended to 9 credential headers after review;
`headers["cookie"]` indexed form gets the "" fallback; `raw_headers["cookie"]` is documented `undefined`; duplicate
`cookie` header fields keep only the last one = pre-existing, tracked as reflex#7521; author's reply on explicitly
constructed `Event(router_data=...)` = intended) and `git show beef0aead` (`reflex/istate/data.py` serializer +
`_HeaderDataVar`; `reflex/state.py` `_load_events_for_page` no longer passes `router_data=state.router_data`; chained
handlers read the producing view from `EventContext.router_data`, `base_state_processor._execute_event`).

### App `src/rtr` + driver `drivers/rtr_drive.py` + proxy `drivers/hdr_proxy.py`
* `RS` records, for every on_load flavour and for a regular handler (`probe`), what it sees in `self.router`
  (`page.path/raw_path/full_path/params/host`, `url`, `url.path`, `url.query_parameters`, `route_id`, `headers.host/origin/
  user_agent`, cookie NAMES, booleans "backend sees the plain cookie / the HttpOnly cookie / Authorization /
  Cf-Access-Jwt-Assertion / X-Forwarded-Access-Token", `len(raw_headers)`, `session.client_token/session_id/client_ip`,
  worker pid) as a JSON line in `RS.log` (secrets reduced to booleans, so the state never carries one).
* Pages: `/` (single on_load), `/multi` (list incl. another state's handler), `/chain` (`yield Other.chained` +
  `return RS.returned`), `/bg` (background task from on_load, yields a frontend event + a backend event), `/redir`
  (on_load returns `rx.redirect("/target?from=redir")`), `/redir-chain` (-> `/redir?hop=1` -> `/target`), `/target`,
  `/post/[slug]`, `/files/[[...splat]]`, `/fe` (on_load list = `rx.console_log`, `rx.call_script(callback=...)`, handler:
  frontend events emitted from an on_load), `/front` (frontend rendering: `State.router.page.path/.params`, `.url`,
  `.url.query_parameters`, `.headers.user_agent`, deprecated `.headers.cookie`, `.headers["cookie"]`,
  `.headers.cookie.contains(..)`, `.headers.raw_headers["cookie"]/["authorization"]`, `.raw_headers.get("cookie","")`,
  `.raw_headers.to_string()`, `rx.foreach(raw_headers)`, `.headers.to_string()`, `.session.client_ip/.client_token`,
  `State.router.to_string()`, computed vars over `self.router`, `State.router.headers` and `.headers.cookie` passed back
  as EVENT ARGS), `/sync` (sync=True LocalStorage -> `update_vars_internal` in the other tab).
* `/setck` = Starlette route via `api_transformer` that sets an **HttpOnly** cookie `rtr_httponly`; the driver also adds a
  plain cookie `rtr_plain` (context cookie).
* Credential headers: Chromium does not apply Playwright `extra_http_headers` to the websocket upgrade (verified: backend
  saw no `authorization`), and refuses `Proxy-Authorization` there outright (`net::ERR_INVALID_ARGUMENT`). So
  `drivers/hdr_proxy.py` sits in front of the backend (dev: 8143 -> 8142, `REFLEX_API_URL=http://localhost:8143`; prod:
  browser loads 3145 -> 3144) and injects `Authorization`, `Proxy-Authorization`, `Cf-Access-Jwt-Assertion`,
  `X-Forwarded-Access-Token`, `X-Auth-Request-Access-Token`, `X-Amzn-Oidc-Accesstoken`, `X-Amzn-Oidc-Data`,
  `X-Goog-Iap-Jwt-Assertion` into every request head incl. the websocket upgrade (= an auth proxy in front of the app).
* Driver walk (37 steps dev / 35 prod): first load, reload, probe, client nav (`rx.link`) to every on_load page incl.
  query change on the same dynamic route and both redirect chains, back/back/forward, direct loads (`goto`) of dynamic,
  catch-all (+query), redirect chain, `/fe`, `/bg`, `/multi`, `/chain`, `/front` (frontend fields read from the DOM),
  event args, second tab (own token, own route), sync=True write in each tab, and in dev a backend hot reload (append a
  comment to the app module) = websocket reconnect + rehydrate, then probe + nav. Captures EVERY websocket frame (both
  directions, `*.frames.jsonl`), every document response body, DOM HTML, storage, console, failed requests; scans all of
  them for the 10 secret values.
* Rerun: `scripts/run_rtr.sh <venv> dev <label> 3142 8142 8143` / `scripts/run_rtr.sh <venv> prod <label> 3144 3144 3145` /
  `scripts/run_rtr_redis.sh <venv> <label>` (prod + `redis-server --port 8149`, app 3146, proxy 3147, 9 granian workers);
  compare: `$DRV drivers/cmp_rtr.py results/rtr/a4dev.json results/rtr/a5dev.json` (volatile token/sid/pid/ws-key masked).

### Results
| check | a4 (control) | **a5** |
|---|---|---|
| backend `self.router` view in every on_load / chained / returned / background / redirected / dynamic / catch-all handler and in `probe`, 37 steps dev, 35 prod, 35 prod+Redis | reference | **identical to a4 on every step and field** (`results/rtr/cmp_{dev,prod,prodredis}_a4_a5.txt`: "log/url diffs=0") |
| backend still sees plain + HttpOnly cookie and Authorization / Cf-Access / X-Forwarded-Access-Token (`self.router.headers.cookie`, `raw_headers[...]`, computed vars `cv_has_cookie`/`cv_has_auth`) | yes | **yes, every step**, incl. prod+Redis where full loads landed on 8 different workers (state from Redis) |
| secrets in received websocket frames (dev / prod / prod+Redis) | **all 10 leak**: 20-21 / 17-18 / 17-18 frames each (hydrate deltas `rx_router_headers.cookie` + `raw_headers`, and on_load frontend events `_call_function` / `_call_script` carrying full `router_data` incl. `headers` / `sid` / `token` / `ip`) | **0 / 0 / 0** for all 10 (cookie, HttpOnly cookie, Authorization, Proxy-Authorization, Cf-Access-Jwt-Assertion, X-Forwarded-Access-Token, X-Auth-Request-Access-Token, X-Amzn-Oidc-Accesstoken, X-Amzn-Oidc-Data, X-Goog-Iap-Jwt-Assertion) |
| on_load frontend events' `router_data` | `_call_function`/`_call_script` from `/fe` on_load: keys `asPath, headers, ip, pathname, query, sid, token` (secret inside) | empty `{}` |
| secrets in sent frames (browser -> server) | 1-2 (the page sends back what it was given: `State.router.headers` / `.headers.cookie` as event args) | 0 |
| after a dev backend hot reload (reconnect, 2 new sockets, 29 frames) | leak | 0 secrets; probe + client nav after reconnect identical to a4 |
| background task deltas, `update_vars_internal` round trip (2 frames), two tabs | leak via the hydrate deltas | 0 secrets; values/behaviour identical |
| document responses (prerendered HTML) / console messages | 0 / 0 | 0 / 0 |
| DOM (`page.content()` on `/front`) | all 10 secrets rendered | none |
| `State.router.headers.cookie`, `headers["cookie"]` | the cookie string (incl. HttpOnly cookie) | `""` (intended, documented) |
| `headers.cookie.contains("PLAIN")` | yes | no |
| `raw_headers["cookie"]` / `raw_headers["authorization"]` / `raw_headers.get("cookie","")` | the secret | `undefined` (renders empty) / same / `""` — as documented |
| `raw_headers.to_string()`, `rx.foreach(raw_headers)`, `headers.to_string()`, `State.router.to_string()` | include cookie + 8 credential headers | same keys minus exactly the 9 filtered names; everything else identical |
| `user_agent`, `page.path/params`, `url`, `query_parameters`, `client_ip`, `client_token`, computed vars over `self.router` | reference | identical |
| `State.router.headers` passed as an event arg -> handler | dict incl. `cookie` key + raw `authorization` | no `cookie` key, no credential raw headers (`recv` delta) |
| deprecation warning for `State.router.headers.cookie` / `["cookie"]` | none | `DeprecationWarning: State.router.headers.cookie has been deprecated in version 0.9.13 ... (rtr/rtr.py:<line>)` in the SERVER/compile log only, once per call site per compile (4 call sites -> 4 lines; dev: repeated after every hot reload); nothing in the browser console |
| console errors | `/favicon.ico` 404 only (benign) | same |
| server log | deprecations (`RouterData.page`, Radix), granian worker warning, shutdown `Unexpected exit from worker-1` | same + the new cookie deprecation |

Security verdict for #7360: **claim holds** on a5 in dev, prod and prod+Redis(9 workers): no cookie (plain or HttpOnly)
and none of the 8 credential headers reach the browser in any websocket frame (hydrate, on_load events, chained /
background deltas, update_vars_internal, after a reconnect), in the HTML, the DOM or the console; a4 leaks all of them
(positive control). Backend access is unchanged. No functional regression in any on_load / router flow vs a4.

Not covered by the filter (by design, noted): an app can still put a credential into state or an event payload itself,
e.g. a computed var `return self.router.headers.cookie`, or an explicitly constructed `Event(router_data=...)` (PR thread);
duplicate `cookie` header fields keep only the last value server-side (pre-existing, reflex#7521).

### Side finding while building the app (pre-existing, not #7360)
The first version of `src/rtr` had no `rtr/__init__.py` (namespace package). On a4 AND a5 dev the page then fails every
state update: browser console `Cannot process state update: no dispatch function for substate(s)
"reflex___state____state.rtr____other", "reflex___state____state.rtr___rs"` (+ `[Reflex Frontend Exception]` in the
server log), on_load results never render, `is_hydrated` stays false. State names come out as `rtr___rs` instead of
`rtr___rtr___rs`. Adding an empty `__init__.py` fixes it. Same on a4 -> not a #7360 regression; `reflex init` always
creates the file, so this only bites hand-made layouts. Logs: `trimmed/rtr-a5dev-t-1.log`, `trimmed/rtr-a4dev-t-1.log`.
Repro: `scripts/bisect.sh <a4|a5> x` after deleting `src/rtr/rtr/__init__.py`.

### reflex-local-auth 0.5.0 / reflex-google-auth 0.2.0 on a5 (venv `a5_hydration_router-tp-a5`)
`scripts/run_la.sh <venv> <dev|prod> <label> <FP> <BP>` (dev 3150/8150, prod 3152): `drivers/tp/drive_local_auth.py`
(38 checks: register, login, on_load guard redirect to /login and back via `redirect_to`, reload, second tab, fresh context,
logout, session expiry, ...) + `drivers/la_storage.py` (14 storage checks). `scripts/run_gauth.sh <venv> <mode> <label> <FP> <BP> 4`
(google-auth demo, dummy client id; a real Google login cannot complete in this sandbox): bogus `token_response_json`
must be cleared and the protected page must stay locked.

| | a4 dev (`a4_hydration-tp-a4`, back to back) | **a5 dev** | **a5 prod** |
|---|---|---|---|
| local-auth `drive_local_auth.py` | 36/38 | **36/38** | **36/38** |
| the 2 fails | known demo pitfall (`/tp-strict-register` `_validate_fields` subclass override), identical text on a3/a4 | same | same |
| `la_storage.py` (fresh profile writes nothing; login stores `_auth_token`; reload + 2nd tab logged in; logout in tab A -> tab B logged out after reload; bogus token -> /protected redirects to /login; console clean) | 14/14 | **14/14** | **14/14** |
| google-auth bogus token | (a4 pass: cleared) | **cleared on first reload; protected locked** | **cleared; locked** |
(After logout the `_auth_token` localStorage key keeps the old token on a4 and a5 alike — local-auth deletes the session
server-side; not a regression.) Results: `results/p2/la_*.txt`, `results/local_auth/`, `results/gauth/`.

## Part 2 — identified-and-fixed hydration regressions on a5 (positive control first)

### F-002 — first page load must write no client-storage defaults (`scripts/p2_f002.sh` -> `scripts/run_f002.sh`)
f1combo (plain / substate / uuid / clock-var / ComponentState storage, cookie options, sync=True): fresh profile x2,
returning visitor (same build), sync tabs, restart with `src/v2/f1combo` (every default changed), returning visitor, fresh.
Ports prod 3140, dev 3142/8142, prod+Redis 3144 (`redis-server --port 8149`). Results `results/p2/f002_*.txt`, `results/f002/`.

| run | written on a fresh profile (LS / SS / cookies) | v2 returning visitor sees v2 defaults | verdict |
|---|---|---|---|
| **0.10.0a1 prod (positive control)** | LS `cu_ls, wt_ls, wu_ls, wu_sync`; SS `cu_ss, wu_ss`; cookies `wu_ck, cu_ck` (every run) | no (keeps v1 `wu-light`, `cu-light`, `wt-light`) | **bug detected** |
| **a5 prod** | only `theme` | yes (`*-dark-v2`) | pass |
| **a5 dev** | only `theme`, `last_compiled_theme` | yes | pass |
| **a5 prod + Redis** | only `theme` | yes | pass |
| sync tabs (all a5 runs) | tab A write followed by tab B (`sync-from-tabA`) | | pass |

### F-003 — computed var rewriting a storage var at hydration must reach the browser (`scripts/run_cv.sh`, `scripts/run_gauth.sh`)
cvstore variants a-j (`cv/drivers/drive_cvstore.py`), compared line-for-line with the a3 pass's saved summaries
(`2026-10-07-a3/a3_hydration/results/f003/`).

| run | result |
|---|---|
| **0.10.0a1 dev seed 4, variants a b g (positive control)** | `reload [l='bad']` for a/b/g — **bug detected**, byte-identical to the saved a1 summary |
| **a5 dev seed 4, all variants** | `[l='']` everywhere; **identical line for line** to a3-dev-seed4 (the fixed baseline) |
| **a5 dev seed 0, all** | identical to a3-dev-seed0 |
| **a5 prod seed 4, all** | identical to a3-prod-seed4 |
| google-auth bogus token, **0.9.12 dev seed 4 (control)** | `BOGUS` kept after reload / index / client nav / reload2 (driver still sees the failure) |
| google-auth bogus token, **a5 dev / a5 prod seed 4** | cleared (`""`) on the first reload and after nav / reload2; protected page stays locked |
(Procedural: the first a1 control invocation passed `a,b,g` as one argument -> driver `KeyError: 'a,b,g'`; re-run with
space-separated variants in `p2_batch2.sh`, after the a5 cvstore runs.)

### A3-11 — sync=True boot-echo storm, explorer series (`scripts/run_storm.sh <venv> <mode> <runs> <FP> <BP> S 6`, driver `drivers/sync_race.py` Part S)
tab0 + 6 tabs load concurrently while tab0 changes the synced value 5x (250 ms apart). Storm = not converged or >50 frames in
the 2 s quiet window. Summaries `results/p2/storm_{dev,prod}_summary.txt` (`scripts/summ_s.py`), raw `results/sync/`.
Compiled frontend verified per run dir: a3 `state.js` md5 `caea5520` (= a3 wheel template), a5 `b7915eda` (= a5 wheel template).

| | a3 (positive control) | **a5** |
|---|---|---|
| dev 3142/8142 | **3/4 storm** (44k-65k frames, 8.5k-14k in the quiet window, tabs split s3/s4 or s4/s5, localStorage stale in 2 runs) | **0/5 storm**; 5/5 all 7 tabs + localStorage `s5` (the user's last value); 47-57 frames total, 0 in the quiet window |
| prod 3144 | **3/3 storm** (12k-31k frames, tabs split s1/s2 / s2/s3) | **0/4 storm**; 4/4 converge on `s5`; 73-93 frames, 0 quiet |

### A3-12 — on_load stamp loop (`scripts/run_stamp2.sh <venv> <mode> <FP> <BP> <runs /stamp> <runs /same> 6`, driver `drivers/stamp_storm.py`)
`src/syncstamp`: `/stamp`'s on_load writes a per-tab value into a sync=True LocalStorage var; 6 tabs load at once. `/same` = control.
Raw lines in `results/p2/stamp_*.txt`, JSON in `results/stamp/`.

| | a3 (positive control) | **a5** |
|---|---|---|
| dev 6 tabs `/stamp` | **2/2 storm** (62k-132k frames per 5 s window, 441k-770k total, 3 different values across tabs) | **0/3 storm**: 100-159 frames total, 0 per 5 s afterwards, all 6 tabs on ONE value |
| prod 6 tabs `/stamp` | **2/2 storm** (54k-113k per 5 s, 2-4 values) | **0/3 storm**: 82-132 frames, one value |
| `/same` control | quiet (dev, prod) | quiet (dev, prod) |

a5 server logs for every Part 2 run: only the pre-existing shutdown `[ERROR] Unexpected exit from worker-1` (granian) in dev runs.

## Verdicts
| item | verdict on 0.10.0a5 | evidence |
|---|---|---|
| #7360 security claim | **holds** (dev, prod, prod+Redis 9 workers) | 0 secret occurrences in 2x ~300 frames / docs / DOM / console per mode on a5; a4 control leaks all 10 secrets in 17-21 inbound frames + DOM |
| #7360 functional | **no regression** | backend `self.router` snapshots identical a4 = a5 on 37/35/35 steps; only intended frontend differences |
| F-002 | **fixed** | a1 control writes 5 LS + 2 SS + 2 cookies; a5 dev/prod/prod+Redis write nothing |
| F-003 | **fixed** | a1 control `[l='bad']` (byte-identical to saved a1); a5 cvstore identical to the fixed a3 baselines (dev s0/s4, prod s4); google-auth bogus token cleared (0.9.12 control keeps it) |
| A3-11 | **fixed** | a3 3/4 dev + 3/3 prod storm -> a5 0/5 + 0/4, all converge on the last value |
| A3-12 | **fixed** | a3 2/2 dev + 2/2 prod storm -> a5 0/3 + 0/3, one value |
| reflex-local-auth / google-auth | = a4 | 36/38 (known demo pitfall) + 14/14 storage, dev and prod |

## Issues / anomalies
1. (low, intended + documented, behaviour note) `State.router.headers.cookie` / `headers["cookie"]` render `""` and the
   deprecation warning is emitted only in the server/compile log, once per call site per compile (4 lines for 4 call sites;
   repeated after every dev hot reload); nothing reaches the browser console. `raw_headers["cookie"]` / `["authorization"]`
   are `undefined` without a warning (documented in router_attributes.md; author's explicit decision in the PR thread).
   An app that passed `State.router.headers.cookie` as an event argument now receives `""` (consequence of the same change).
2. (low, pre-existing in 0.9.12, a4 and a5; not #7360) An app package without `__init__.py` (namespace package) compiles
   and serves but every state update fails in the browser with `Cannot process state update: no dispatch function for
   substate(s) "reflex___state____state.rtr____other", "reflex___state____state.rtr___rs"` (state names lose the module
   segment); on_load results never render, `is_hydrated` stays false. Repro: `src_noinit/rtr` (= `src/rtr` minus
   `__init__.py`): `scripts/srv.sh start rtr-x <stable|a4|a5> dev $W/src_noinit/rtr 3142 8142; $NP $DRV drivers/dbg_console.py http://localhost:3142/ 5`.
   Logs `trimmed/rtr-a5dev-t-1.log`, `trimmed/rtr-a4dev-t-1.log`, `trimmed/rtr-s912dev-ni-1.full.log`. `reflex init`
   creates the file, so only hand-made layouts hit it; the error message points at a frontend/backend mismatch, not the cause.
3. (harness note) Chromium (Playwright `extra_http_headers`) does not send extra headers on the websocket upgrade and rejects
   `Proxy-Authorization` (`net::ERR_INVALID_ARGUMENT`); use `drivers/hdr_proxy.py` to reproduce credential-header tests.

## Not covered
* reflex-google-auth real login/logout (needs Google; sandbox blocks it) — only the bogus-token / protected-page guard path.
* local-auth / google-auth on prod + Redis; the verifier's raw-CDP background-tab storm scenarios (100 ms RTT proxy) for A3-11/A3-12 (explorer series only, per brief).
* Enterprise auth paths that read `router_data` (`_event_client_token`, page guards) — cluster a5_upgrade_ent.
* Browsers other than Chromium.

## Cleanup
All servers, header proxies, redis-servers and browsers stopped; no listener in 3140-3159 / 8140-8159 / 3660-3679 / 8660-8679;
every run dir's `.web/` (incl. node_modules) deleted (`$W/run` = 12 MB).
