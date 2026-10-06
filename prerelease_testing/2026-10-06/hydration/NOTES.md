# Cluster `hydration`: combined hydrate+connect (#7064), client storage and on_load lifecycle

Published packages under test: `reflex==0.10.0a1` (alpha) vs `reflex==0.9.12` (stable baseline). Everything
was installed from PyPI into the prebuilt read-only venvs `$SB/envs/alpha` and `$SB/envs/stable`.
Nothing came from the checkout. Browser: Playwright 1.63 with Chromium `/opt/pw-browsers/chromium` (`$SB/envs/driver`).
Date: 2026-10-06. Everything ran end-to-end in a real browser on both versions:
* the s1–s13 suite in dev and prod;
* reconnect, redis, latency and pre-connect-navigation tests in prod;
* the hot-reload test in dev.

`SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad` (adjust to your scratch
root). The work dir was `$SB/apps/hydration/`. All artifacts are copied here.

## Headline results

| # | Result | Regression? |
|---|---|---|
| F1 | **First page load now writes client-storage default values into the browser** (localStorage, sessionStorage and cookies). This happens for every state the boot hydrate sends in full, which is any state with a per-process or per-instance default such as `default_factory=uuid4`. A returning visitor then keeps the stale default after the app's default changes. | **YES**, alpha only (0.9.12 writes nothing) |
| F2 | A single localStorage value over the 1 MB socket buffer causes an endless reconnect storm: about 35–39 websocket connects/s, about 1 GB uploaded in 22 s, the page never hydrates, no UI error, and no server log on alpha. | no, both versions |
| F3 | Redis + prod: one of 9 alpha multi-worker (redis, 9-worker) stops had a granian/pyo3 panic during shutdown. The following reconnect got `new_token` and fresh state. In clean restarts state and token survive (alpha 4/4, stable 4/4). | unknown (flaky; same granian 2.8.4 on both) |
| F4 | #7357 verified fixed: while another client's buffered upload is in flight, a navigation now supersedes the previous page's slow `on_load`. On 0.9.12 the stale on_load ran to completion (dev and prod). | fix confirmed |
| F5 | Performance claim confirmed. With 80 ms RTT (`drivers/latency_proxy.py`, interleaved n=12), alpha reaches hydrated **158–180 ms sooner**: `/other` 570.5 vs 728.5 ms, `/` 500 vs 679.5 ms. CONNECT-to-hydrated is 91 vs 178–183 ms (one RTT saved), and the CONNECT is sent about one RTT earlier (warm socket). The boot sends 1 frame out instead of 3 and about 36% fewer inbound bytes (3019 vs 4716). On localhost only the few-ms connect-to-hydrated slice differs (9 vs 12.5–14 ms; end-to-end within noise). The reload flash of compiled defaults is shorter in prod (61 vs 135 ms, one sample). | improvement |
| F6 | **Client-side navigation before the websocket CONNECT is sent runs the page the user LEFT's on_load.** The boot `hydrate_and_load` carries router data captured when `connect()` ran at mount. 0.9.12 instead ran the new page's on_load twice and never the old one. | **YES** (new failure mode; 0.9.12 had a different, pre-existing double-run) |

Everything else in the brief behaves identically on both versions (details below).

## App and scripts

* `hydapp/`: one multi-page app with identical source for both versions.
  * Root user state `State`: `rx.LocalStorage` plain, `LocalStorage(sync=True, name="hyd_sync")`, `SessionStorage`, `Cookie(max_age=3600, path="/")`, an int-annotated `Cookie("5", name="hyd_int")`, a hash-equal `LocalStorage("same-value")` and a large `LocalStorage`.
  * Substate `Sub`: LocalStorage, Cookie(max_age=600), SessionStorage, and a `default_factory=uuid4` var. Its `sub_ls` default is env-driven by `HYD_SUB_LS_DEFAULT`; this was added mid-run, and the default is unchanged when the env var is unset.
  * Substate `Clean`: storage only, deterministic defaults.
  * `LsLoad`: has its own on_load and its own LocalStorage.
  * `Defaults`: uuid and datetime factories, env default, `list` default mutated at import and in a lifespan task, dict, dataclass, float, pid-based default, computed var.
  * `StorageBox(rx.ComponentState)` with LocalStorage, two instances.
  * Pages: `/` (on_load reads all storage and records what it saw), `/redir` (on_load returns `rx.redirect`), `/bgload` (background on_load), `/raise` (on_load raises), `/slow` (async-generator on_load, 4 deltas 2 s apart), `/multi` (`on_load=[State.multi_a, Sub.multi_b]`), `/script` (on_load returns `rx.call_script(..., callback=...)`), `/items/[id]`, `/docs/[[...splat]]`, `/lsload`, `/defaults`, `/clickfast` (1 s on_load, always-visible and `is_hydrated`-gated buttons), `/gate` (`rx.cond(State.is_hydrated, content, spinner)`), `/upload` (buffered upload handler in flight for 7 s), `/nested`.
  * Handlers print `HYDTRACE <time> <token8> <msg>` to the server log and append to `State.trace`, which the page shows as JSON.
* `mini_writeback/`: minimal standalone repro for F1. One state with `LocalStorage`, `Cookie` and a `default_factory=uuid4` var. The theme default is env-driven by `MINI_THEME_DEFAULT`.
* `scripts/srv.sh`: start/stop helper (`setsid` process group; copies `hydapp` into `$SB/apps/hydration/run/<name>`; sets `REFLEX_TELEMETRY_ENABLED=false` and `REFLEX_API_URL`; `--loglevel debug`). Stop sends SIGTERM to the process group and verifies the ports are free with `lsof`. `scripts/mini.sh` is the same for the mini app.
* `drivers/`, run with `$SB/envs/driver/bin/python` and the client-side `NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1`:
  * `hyd_driver.py`: scenarios s1–s13. Each runs in a fresh context and captures console messages (all types), page errors, failed requests, HTTP ≥400, socket.io frames with namespace-aware decoding of which states and vars each delta carried, a client DOM timeline (MutationObserver per tracked id, with `performance.now()`), and screenshots.
  * `reconnect_driver.py`: kills and restarts the prod server with a tab open (memory/disk/redis), runs an offline flap, and optionally runs the default-change visitor test.
  * `redis_restart_loop.py`: repeated redis restarts; checks leftover token keys, shutdown panics and token/state survival.
  * `token_leak_check.py`: checks for redis token keys left after a stop.
  * `preconnect_click.py`: holds the backend websocket 2.5 s with `route_web_socket` and clicks before the CONNECT.
  * `hmr_desync.py`: dev hot reload with the memory manager while a tab is open.
  * `ab_timing.py`: interleaved A/B first-load timing against two prod servers.
  * `prenav_test.py`: client-side navigation while the websocket is held (F6).
  * `prenav_natural.py`: the same without the hold, behind `latency_proxy.py`, a TCP proxy adding a fixed one-way delay.
  * `mini_writeback_check.py`, `waitsrv.py`.

### Ports

* alpha dev: 3220/8220
* stable dev: 3222/8222
* alpha prod: 3221 (single port)
* stable prod: 3223 (single port)
* mini app prod: alpha 3224, stable 3225
* redis: 8239
* 80 ms-RTT proxies: 3226 → 3221 (alpha) and 3227 → 3223 (stable); the servers were started with `REFLEX_API_URL=http://localhost:3226` and `:3227`

### Rerun commands

```bash
SB=...; H=$SB/apps/hydration           # copy hydapp/, mini_writeback/, drivers/, scripts/*.sh here
NP="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1"
# full scenario suite (dev, then prod) for each version
$H/srv.sh start alpha-dev alpha dev 3220 8220
$NP $SB/envs/driver/bin/python $H/drivers/waitsrv.py 360 http://localhost:3220/ http://localhost:8220/ping
$NP $SB/envs/driver/bin/python $H/drivers/hyd_driver.py --base http://localhost:3220 --label alpha-dev --out $H/results/alpha-dev
$H/srv.sh stop alpha-dev
$H/srv.sh start stable-dev stable dev 3222 8222   # ... same with --base http://localhost:3222
$H/srv.sh start alpha-prod alpha prod 3221 3221   # ... --base http://localhost:3221
$H/srv.sh start stable-prod stable prod 3223 3223 # ... --base http://localhost:3223
# reconnect scenarios (the driver starts and stops its own server)
$NP $SB/envs/driver/bin/python $H/drivers/reconnect_driver.py --venv alpha --port 3221 --manager memory --out $H/results/reconnect-alpha-memory --default-change
#   also: --manager disk ; --manager redis (needs: redis-server --port 8239 --save '' --appendonly no &)
$NP $SB/envs/driver/bin/python $H/drivers/redis_restart_loop.py alpha 3221 4
# interleaved timing (two prod servers briefly)
$H/srv.sh start ab-alpha alpha prod 3221 3221; $H/srv.sh start ab-stable stable prod 3223 3223
$NP $SB/envs/driver/bin/python $H/drivers/ab_timing.py http://localhost:3221 alpha http://localhost:3223 stable 20 /other out.json
# F6 (one prod server at a time): navigation before the websocket CONNECT
$H/srv.sh start alpha-prenav alpha prod 3221 3221
$NP $SB/envs/driver/bin/python $H/drivers/prenav_test.py http://localhost:3221 alpha-prod prenav_alpha.json 2000
$H/srv.sh stop alpha-prenav    # then the same with stable on 3223
# click before CONNECT / dev hot reload (dev servers; memory manager for the HMR test)
$NP $SB/envs/driver/bin/python $H/drivers/preconnect_click.py http://localhost:3220 alpha-dev out.json 2500
$H/srv.sh start alpha-dev-hmr alpha dev 3220 8220 REFLEX_STATE_MANAGER_MODE=memory
$NP $SB/envs/driver/bin/python $H/drivers/hmr_desync.py http://localhost:3220 $H/run/alpha-dev-hmr/hydapp/hydapp.py hmr_alpha.json
```

The driver guard is `sys.executable` = driver venv. Each app server runs `$SB/envs/<alpha|stable>/bin/reflex` from
`$H/run/<name>`, which is a neutral directory and not the checkout. Module origins were checked in
`probe/probe_cookie_int.py`, which asserts `reflex.__file__` is under `/scratchpad/envs/<venv>/`.

## Scenario matrix (s1–s13; `results/<mode>/<scenario>.json`)

| scenario | alpha-dev | stable-dev | alpha-prod | stable-prod |
|---|---|---|---|---|
| s1 storage set → reload → restored; on_load saw restored values | pass | pass | pass | pass |
| s1b which client-storage keys a fresh first load writes | **anomaly (F1)** | pass (none) | **anomaly (F1)** | pass (none) |
| s2 two tabs, `sync=True` both ways; token per tab; `window.open` duplicate; new context | pass | pass | pass | pass |
| s3 clear storage via JS + `clear_cookies` → reload → defaults (on_load saw defaults); `rx.remove_local_storage` | pass | pass | pass | pass |
| s4 int-annotated Cookie set to `abc` from JS | anomaly (same) | anomaly (same) | anomaly (same) | anomaly (same) |
| s5 300k-char localStorage OK; 1.2M chars: storm (F2) | pass / F2 | pass / F2 | pass / F2 | pass / F2 |
| s6 redirect (direct + client), bg on_load, raising on_load, `on_load=[A,B]`, call_script callback, LsLoad (direct + client nav) | pass | pass | pass | pass |
| s6b slow on_load superseded by link nav and by browser back; forward re-runs | pass | pass | pass | pass |
| s7 `is_hydrated` gate flips to yes exactly once (direct, client nav, reload) | pass on rerun* | pass | pass | pass |
| s8 defaults: displayed == backend values; distinct per-session ids | pass | pass | pass | pass |
| s9 `/items/[id]` direct, nav, back, forward; catch-all `/docs/[[...splat]]` | pass | pass | pass | pass (HTTP 404 on direct loads, pre-#6996) |
| s10 click during on_load (after connect) | info (same) | info (same) | info (same) | info (same) |
| s11 #7357 upload in flight + other client's nav supersedes slow on_load | pass | **fail** | pass | **fail** |
| s12 event list + failing `rx.set_value` then a normal event | pass | pass | pass | pass |
| s13 timing (single-version, noisy; see F5 for interleaved) | n/a | n/a | n/a | n/a |

\* The first alpha-dev s7 run "failed" because of a driver artifact: it clicked the next link while home's own on_load was
still finishing. After fixing the driver, the alpha-dev rerun (`results/alpha-dev-rerun/s7.json`) passes.

No console errors or warnings, page errors, failed requests or HTTP ≥400 occurred in any alpha scenario (benign
React Router/vite/DevTools lines are filtered). Stable prod s9 logs three HTTP 404 document responses for direct
dynamic-route loads. That is the pre-existing behavior fixed in alpha by #6996 (SPA fallback 200).

### Details per brief item

1. **Client storage** (s1, s1b, s2, s3, s4, s5)
   * Values set through the UI are written to storage. After reload they are restored, and the page's on_load sees them before it runs, e.g. `index_load#2 ls=ls-A|sync=sync-A|ss=ss-A|ck=ck-A|...|sub_ls=sub-ls-S1|sub_ck=sub-ck-S1`. This holds for the root state, a substate and a ComponentState instance (box a restored; box b keeps its default).
   * Hash-equal case: the browser stores exactly the default (`hyd_same=same-value`). It is not re-sent, and the display is correct.
   * `sync=True` propagates A→B (UI set) and B→A (JS `localStorage.setItem`).
   * Clearing storage, then reloading, gives defaults on the frontend and the backend; on_load saw the defaults.
   * `rx.remove_local_storage` re-runs the full hydrate and the on_load handlers (load_count 2→3) on both versions.
   * Wrong-type cookie (`hyd_int=abc` for `ck_int: int = rx.Cookie("5")`) is graceful on both: no traceback on hydrate, value `abc` displayed, `ck_int + 1` renders `abc1` (string concat), and the backend handler `self.ck_int + 1` raises TypeError. Even the str default `"5"` renders as `51`. Both versions also log `Expected field 'State.ck_int' to receive type int, but got '5' of type Cookie` on every hydrate (client-storage defaults are str subclasses). This is pre-existing API looseness, low.
2. **on_load** (s6, s6b, s7, s10, s11)
   * Redirect: final URL `/other` and trace `['redirect_load', 'other_load#1']`.
   * Background on_load: `idle → started → done` over 1.5 s, and the page hydrates at about 0.14 s.
   * Raising on_load: the backend traceback is logged, the page still reaches `is_hydrated` and stays usable.
   * `on_load=[A,B]`: order A then B, and B (substate) saw the root's browser-restored LocalStorage value.
   * `call_script` callback: delivers `42`.
   * Slow on_load: navigating away by link or by browser back at step 2 stops it at 2 on both versions (`Cancelling the previous unfinished ... on_load_internal chain` in the debug log).
   * `is_hydrated` gate: on direct load and reload, no gated content appears before hydration and the flag flips once.
   * Client-side navigation from a hydrated page renders the gated content for about 4–6 ms. The new route first renders with the old page's `is_hydrated=true`, then the location effect dispatches `false`. This happens on both versions; pre-existing, cosmetic.
3. **Defaults** (s8, frames in `s1b.json`)
   * First delta on alpha: root partial (router vars only); `Sub` and `Defaults` sent in full (non-deterministic defaults make the per-state hash differ); `Clean`, `State` and the ComponentStates are omitted (hash-equal and at default).
   * Every displayed value equals the backend value after hydration, in dev and prod, including the lifespan-mutated list, which the bundle did not have.
   * First paint briefly shows the compiled bundle values. For example, the uuid generated at build time appears for about 100 ms for every visitor, the same on both versions.
4. **Reconnect** (`results/reconnect-*`)
   * The kill shows the "Cannot connect to server" banner on both versions.
   * Memory manager: after restart, counter 0 (state gone); client storage is re-applied from the browser by exactly one `hydrate_and_load` (no hashes); on_load re-runs once; the flag goes no→yes once. Same on stable, which sends 3 events.
   * Disk manager: `reflex run --env prod` logs `Resetting disk state manager` at startup, so state does not survive on either version (by design).
   * Redis: state and token survive on clean restarts on both versions, except F3.
   * `context.set_offline(True)` does not drop an established websocket in Chromium, so it was a no-op on both versions.
5. **Multi-tab** (s2)
   * The brief's premise doesn't hold: the token lives in sessionStorage, so two tabs of one context get different tokens and states.
   * `window.open` copies the token; the backend's duplicate detection gives the new tab a fresh token.
   * A new context gets its own token. Same on both versions.
6. **Dynamic routes** (s9): `params["id"]`, `router.url` and the catch-all `splat` are correct on direct load, client nav, back and forward. Same on both.
7. **Event delivery during hydrate** (s10, `preconnect_click.py`)
   * A click during the 1 s on_load, after connect, is processed after the on_load, with `loaded=True, hyd=True`.
   * A click made before the websocket CONNECT (socket held 2.5 s) is also processed after the on_load. On alpha the server-side chain enqueues `on_load_internal` before the click arrives.
   * Same on both versions; nothing is lost or duplicated.
8. **on_load on a state that owns LocalStorage** (s6 `lsload`): the handler saw the browser value on direct load and after client nav (`saw=lsl-from-browser`, `saw=lsl-changed-before-nav`). Same on both.
9. **Dev hot reload** (`hmr_desync.py`, memory manager): editing a compiled default with a tab open reconnects with a full hydrate (no hashes), and counter 3 → 0 matches the backend. There is no stale-UI desync on either version.

## F1: client-storage defaults persisted on first load (REGRESSION)

**Mechanism (from frames, `results/*/s1b.json` and `s1b.raw.json`)**
* Alpha's boot delta diffs the snapshot against the compiled defaults. The root state is present (router vars changed) but `is_hydrated_rx_state_` is dropped, because `False` equals its compiled default.
* `applyClientStorageDelta` in `state.js` only skips writing client storage when the main state carries `is_hydrated_rx_state_ === false`. It therefore writes every client-storage var in the delta to the browser.
* For states sent in full (hash mismatch), that includes the reset defaults the user never set.
* Stable's `hydrate` delta is a full dict whose root contains `"is_hydrated_rx_state_":false` (frame prefix `{"delta":{"reflex___state____state":{"id_rx_state_":"","is_hy...`), so the write is skipped.
* The `hydrate_and_load` source comment itself says: *"The snapshot must carry is_hydrated=False: the frontend skips writing client storage for a delta that is not yet hydrated, and the reset defaults above must not be written back to the browser."* The diff violates that.

**Minimal repro** (`mini_writeback/`, prod; `drivers/mini_writeback_check.py`):

```bash
$H/mini.sh start alpha 3224
$NP $SB/envs/driver/bin/python $H/drivers/waitsrv.py 580 http://localhost:3224/ http://localhost:3224/ping
$NP $SB/envs/driver/bin/python $H/drivers/mini_writeback_check.py http://localhost:3224/ - /tmp/state.json
#   alpha : {"theme_shown": "light", "localStorage": {"mini_theme": "light"}, "cookies": "mini_consent=unset"}
#   stable: {"theme_shown": "light", "localStorage": {}, "cookies": ""}
$H/mini.sh stop alpha; $H/mini.sh start alpha 3224 MINI_THEME_DEFAULT=dark   # deploy with a new default
$NP $SB/envs/driver/bin/python $H/drivers/mini_writeback_check.py http://localhost:3224/ /tmp/state.json   # returning visitor
#   alpha : theme_shown "light" (stale default now stored as if user-chosen); fresh visitor: "dark"
#   stable: theme_shown "dark" for both returning and fresh visitors
```

The same happens in the full app, in dev and prod (s1b, `reconnect-alpha-memory/result.json`):
* After one visit: `hyd_sub_ls=sub-ls-default` (localStorage), `hyd_sub_ss=sub-ss-default` (sessionStorage), `hyd_sub_ck=sub-ck-default` (cookie, max_age 600).
* Returning visitor after `HYD_SUB_LS_DEFAULT=sub-ls-NEWDEFAULT`: alpha shows `sub-ls-default`, stable shows `sub-ls-NEWDEFAULT`.
* The written values are then sent back in every later `hydrate_and_load` as if user-set (`hmr_alpha.json` boot vars).

**Impact**
* Cookies and storage are set without any user action, which is a consent and privacy concern.
* Default changes no longer reach returning visitors.
* The damage persists after a fix, because written defaults become indistinguishable from user choices.

**Trigger:** any state with client-storage vars that the boot hydrate sends in full, i.e. it has any default that differs between the compiling process and the backend (`default_factory` uuid/time, import-time time/pid/env values, and probably set-typed vars under hash randomization). In this environment it reproduced in dev too.

**Fix idea:** never diff out the root `is_hydrated` (or send it explicitly in the boot delta), or make the frontend skip client-storage writes for the boot delta.

## F6: navigation before the socket CONNECT → the left page's on_load runs (alpha) / the new page's on_load runs twice (0.9.12)

`drivers/prenav_test.py` (results `results/prenav_{alpha,stable}.json`, backend traces `logs/*-prenav-1.hydtrace.log`)
holds the backend websocket for 2 s with Playwright `route_web_socket`. In prod, it loads `/slow` (or `/items/1`) and clicks
the client-side link to `/other` (or `/items/2`) before the CONNECT is sent.

| start → target | 0.10.0a1 backend trace | 0.9.12 backend trace |
|---|---|---|
| `/slow` → `/other` | `slow_load run1 step1`, then `other_load#1`. The left page's on_load starts, its first delta (`slow_progress=1`) lands on `/other`, and the rest is cancelled | `other_load#1`, `other_load#2` (new page's on_load twice) |
| `/items/1` → `/items/2` | `item_load id=1` (`path=/items/1`, run after the user left), then `item_load id=2` | `item_load id=2` twice |

Both versions reproduced 2/2. The page ends on the right URL and hydrated on both.

* **Cause (alpha):** `state.js` `connect()` sets `socket.current.auth = bootAuth(true)` once, when the event loop mounts. `withRouterData` therefore snapshots the location at mount, and the CONNECT packet (sent after the engine.io handshake) still names the old page. The backend hydrates as that page and chains its `on_load_internal`. That chain runs before the navigation's `on_load_internal` arrives one round trip later, which can then only supersede what is still unfinished. 0.9.12 attached router data at send time, after connect, so the queued boot `hydrate`+`on_load_internal` and the navigation's `on_load_internal` both named the new page.
* **Impact:** side effects of an on_load (record a view, start a job, mark something read) run for a page the user already left, and its early deltas render on the new page.
* **Window:** clicking a link before the websocket handshake completes, i.e. slow mobile RTT, a backend slow to accept websocket connections, or a cold start.
* **Fix idea:** make `auth` a function (socket.io calls it at connect time) or refresh `socket.current.auth` from the location effect while not yet connected.
* **Natural reproduction check:** `drivers/prenav_natural.py` ran behind the 80 ms RTT `latency_proxy.py` (4 runs per version), clicking `/items/2` as soon as React had hydrated the link. The CONNECT had already been sent every time on both versions, so both behaved identically (`id=1` then `id=2`). The window needs the websocket handshake to lag behind page interactivity, e.g. a backend slow to accept websocket connections, a cold start or scale-from-zero while the prerendered frontend is already served, or a slow websocket proxy. `route_web_socket` simulates exactly that.

## F2: oversized localStorage value → endless reconnect storm (pre-existing)

* Set `localStorage['hyd_big']='x'.repeat(1200000)`, then reload (s5; `results/s5_storm_summary.json`). Alpha puts the 1.2 MB value in the socket.io CONNECT packet. Engine.IO's `maxPayload` is 1,000,000 (`REFLEX_SOCKET_MAX_HTTP_BUFFER_SIZE`), so the server closes the connection, and the `disconnect` handler reconnects immediately with no backoff.
* Alpha: 819–866 connects in about 22 s (≈37–39/s), ≈1 GB uploaded, page stuck at compiled defaults with `H:no`, no banner, no console error, and nothing in the server log (the boot never reaches a handler).
* 0.9.12: same loop at ≈34/s, ≈0.9 GB. The connect succeeds, then the 1.2 MB `update_vars_internal` event kills it. It logs about 750 `Expected field` lines from the repeated hydrates.
* 300k chars works on both versions.
* Severity medium, not a regression. One oversized storage value bricks the app for that browser and floods the backend.

## F3: redis + prod restart lost token and state once (granian shutdown panic)

* In `reconnect-alpha-redis/result.json`, the first stop of the 9-worker prod server logged:
  `thread 'tokio-rt-worker' panicked at .../pyo3-0.29.2/src/internal/state.rs:330:9: Cannot drop pointer into Python heap without the thread being attached.` (`logs/recon-alpha-redis-1.shutdown-tail.log`).
* After restart the tab's boot got `42/_event,["new_token","4b03e19f-..."]`. The redis `token_manager_socket_record_<token>` key apparently survived, so duplicate detection fired and the user saw fresh state: counter 0, new token.
* `redis_restart_loop.py`: alpha 4/4 and stable 4/4 clean restarts kept token and state, with no leftover keys and no panic. `token_leak_check.py`: alpha 2/2 clean.
* That makes 1 panic in 9 alpha multi-worker stops and 0 in 7 stable stops. Both venvs use granian 2.8.4, so regression status is unknown; likely a flaky granian shutdown race whose redis-side consequence is that clients get reassigned tokens.
* Also benign on both versions: with redis, prod spawns 9 workers on 4 CPUs (`[WARNING] Configured number of workers appears to be higher than the amount of CPU cores`).

## F4: #7357 fix confirmed

* s11: client X starts a buffered upload whose handler stays in flight 7 s. Client Y loads `/slow` and clicks to `/other` at step 2.
* Alpha (dev and prod): Y's slow on_load stops at 2.
* 0.9.12 (dev and prod): it continues to `step4` and `finished` after Y left (`results/*/s11.json`).

## Benign or other observations

* `Warning: Attempting to send delta to disconnected client`: a slow on_load keeps running after its tab closes. Same on both versions.
* `[ERROR] Unexpected exit from worker-1` once on alpha dev shutdown. It is an artifact of SIGTERM reaching the granian worker and main process together through the process group.
* `DeprecationWarning: RouterData.page` comes from the app's intentional use of `router.page.params`.
* Two `is_hydrated:false` deltas per boot: one in the snapshot (only when not diffed out), one from `on_load_internal`. Harmless; also on stable.
* The dead `on_hydrated_queue` in `state.js` connect() is never pushed to. It is pre-existing code, already present in 0.9.12.
* The disk state manager is reset by every `reflex run --env prod`, on both versions.
* While the server is down in the reconnect runs, the console shows the expected `WebSocket connection ... failed: net::ERR_CONNECTION_REFUSED` lines (about 10 per outage, incremental backoff), on both versions.

## NOT covered

* Build-env ≠ runtime-env defaults (`reflex export` frontend with a backend started separately under different env). The hash mismatch path itself is exercised by `Sub` and `Defaults`.
* Real network conditions beyond a fixed 80 ms RTT proxy (no bandwidth cap, loss or mobile profiles).
* bfcache restore.
* Multiple browsers.
* Frequency of the F3 panic beyond 16 multi-worker stops (9 alpha, 7 stable).

## Provenance notes

* The server logs' tracebacks resolve framework frames under `.../scratchpad/envs/alpha/lib/python3.12/site-packages/reflex_base/...` and `.../envs/stable/...` respectively (e.g. `logs/alpha-prod-1.trimmed.log`). Apps were run from `$SB/apps/hydration/run/<name>`, never from the checkout.
* The archived `hydapp.py` and `mini_writeback.py` have a venv guard (`assert "/envs/alpha/" in rx.__file__ or "/envs/stable/" in rx.__file__`). It was added after the runs, is functionally neutral, and should be adjusted if your venv paths differ. The drivers never import reflex.
* `results/<mode>/*.raw.json` (console, page errors, HTTP errors, websocket frames) are kept for s1, s1b, s10, s11 and s13. The 4–7 MB s5 raw captures were reduced to `results/s5_storm_summary.json`.

## VERIFICATION — F1/F6

Independent verifier, 2026-10-06. I did not read the explorer's transcript, only the artifacts in this folder.
* Venvs: the shared read-only `$SB/envs/alpha` (reflex 0.10.0a1) and `$SB/envs/stable` (0.9.12). Drivers ran with `$SB/envs/driver`.
* Work dir: `$SB/apps/verify_hydration_0`.
* Ports: alpha prod 3720, stable prod 3721, alpha dev 3722/8722. Upgrade-delay proxies: 3722→3720 and 3723→3721.
* My files are in `verification/`:
  * `scripts/`: `vsrv.sh` start/stop, `proxy.sh`, `summ.py`.
  * `f1-client-storage-defaults/{apps,drivers,results,logs}`.
  * `f6-prenav-onload/{drivers,results,logs}`.
* Line numbers below refer to the published files under `$SB/envs/<venv>/lib/python3.12/site-packages/`.

### F1: CONFIRMED, regression, but the trigger is narrower than "first page load"

**The written repro works as written.** The only changes were my ports and dirs.

| run | localStorage / cookie after the visit | displayed theme |
|---|---|---|
| alpha prod, fresh | `mini_theme=light`, `mini_consent=unset` | `light` |
| alpha prod, restarted with `MINI_THEME_DEFAULT=dark`, returning visitor | stays `light` | **`light`** (fresh visitor: `dark`) |
| alpha dev, fresh (2/2) | `mini_theme=light`, `mini_consent=unset` | `light` |
| 0.9.12 prod, fresh | nothing | `light` |
| 0.9.12 prod, restarted with dark, returning visitor | nothing | `dark` |

The returning visitor's CONNECT on alpha carries `vars={theme:'light', consent:'unset'}`. The persisted defaults come back to the backend as if the user had set them. Results: `f1-client-storage-defaults/results/f1_mini_*.json` and `mini_*_state1.json`.

**Frames.** `drivers/f1_check.py` decodes the received socket.io deltas.
* Alpha's first delta has root `reflex___state____state` = the five `rx_router_*` vars only. `is_hydrated_rx_state_` is **absent**.
* The user state is in the same delta in full: `consent`, `theme`, `visitor_id`.
* A second delta then carries `is_hydrated_rx_state_: true`.
* 0.9.12's `hydrate` delta root carries `is_hydrated_rx_state_: false`, plus every state with every storage var. Its frontend therefore skips the write.

**My own minimal apps** (`apps/f1plain`, `apps/f1combo`; alpha prod, 2/2 identical each):

| state shape | sent in full on boot? | defaults written to browser? |
|---|---|---|
| `f1plain.Prefs`: ONE state with `LocalStorage("light")`, `Cookie("unset")`, `SessionStorage("x")`, no factory/env | no; the state is not in the delta at all | **no** (nothing written) |
| `Plain`: storage only, deterministic | no | no |
| `WithUuid`: storage + `default_factory=uuid` in the same state | yes | **yes**: LS, sync-LS, SS, and the cookie with a real `max_age` expiry |
| `ChildStorage`: storage-only substate whose parent has a uuid factory | no (only the parent is sent) | no; the trigger is per state, not inherited |
| `ChildStorageUuid`: storage + uuid on a substate, deterministic parent | yes | **yes** |
| `WithClockVar`: storage + a cached `@rx.var` returning `time.time_ns()`, no factory | yes | **yes**; computed vars trigger it too |
| `WithSet`: storage + `set[str]` default | no, in this setup | no. In this run the backend serialized the set in the same order as the compiled default (why was not investigated), so whether `set[str]` triggers it in other deployments is untested |

0.9.12 with the same `f1combo` app writes nothing.

**Returning visitor after a source-level release with new defaults** (`apps/f1combo_v2`, which changes every default; same browser storage as the v1 visit):
* Alpha shows the v1 values for every triggered state: `wu-light`, `wu-sync-default`, `cu-light`, `wt-light`, cookies `wu-unset`/`cu-unset`.
* Untriggered states (`Plain`, `ChildStorage`) show v2.
* A fresh visitor sees v2.
* 0.9.12 shows v2 for everyone.

**`sync=True` across two tabs** (`drivers/f1_sync_tabs.py`, `results/f1_sync_tabs_*.json`):
* Opening a second tab normally fires no storage events on either version. Alpha's second tab rewrites the value tab A's boot already persisted, and 0.9.12 writes nothing.
* Race: tab B2's socket is held 2.5 s while tab A changes the synced var.
  * Alpha, 2/2: B2's full-sent boot delta rewrites the stale mount-time value. Tab A gets storage event `sync-from-tabA → wu-sync-v2` and sends `update_vars_internal`, so its backend value is reverted. About 10 ms later it is restored by B2's queued storage event.
  * The result is a transient revert plus 2 extra round trips; it converges.
  * 0.9.12: no events, no revert.

**Mechanism** (published sources; confirms the explorer):
* `reflex/state.py:2339-2345`: `hydrate_and_load` resets client storage and applies browser `vars`. Then it sets `is_hydrated=False`, with the comment that the frontend must skip storage writes for this delta.
* `:2348-2351`: snapshot, then `_diff_against_initial_state`.
* `:2497-2501`: a state whose per-state hash differs is sent in full, including the reset defaults.
* `:2503-2509`: for hash-matched states, vars that serialize equal to the default are dropped. That includes the root's `is_hydrated_rx_state_` (False == default).
* The root stays in the delta because the router vars changed.
* `reflex_base/.templates/web/utils/state.js:1045-1060` (`applyClientStorageDelta`) returns early only if `is_hydrated_rx_state_ !== undefined && !is_hydrated_rx_state_`. Otherwise `:1061-1090` writes every cookie/LS/SS var in the delta.
* It is called for every delta at `:896`.
* Safe paths: a whole-list hash mismatch returns the full delta (`state.py:2490-2492`), and reconnects send no hashes (`initialEvents(first)` in the compiled `.web/utils/context.jsx`). Both keep `is_hydrated:false`, so the bug is specific to "root diffed + some storage state sent in full".
* 0.9.12 for comparison: `reflex/state.py:2935-2951` (`hydrate` emits the full dict with `is_hydrated=False`), and stable `state.js:903` has the same skip check.
* PR #7064's description and changelog promise only "send only values that differ from compiled defaults". Nothing documents writing storage.
* `main` (`origin/main`, 62a56ba7f) still has the same code.

**Harm assessment: not cosmetic.**
1. **Stale defaults for returning visitors.** Once written, a default is indistinguishable from a user choice, because it comes back in `vars` on every boot. A new release that changes a default no longer reaches anyone who visited once. localStorage never expires.
2. **Cookies and storage the user never caused.** They are set on the first visit, and a `max_age` cookie gets a real expiry, refreshed on each boot that sends the state in full. That is a consent/compliance concern, and those cookies ride on every HTTP request.
3. **The effect outlives a fix.** Browsers that visited an affected release keep the values.

The trigger is per state class: client-storage vars plus any default or cached computed var that serializes differently in the compiling process and the backend worker. Examples are a uuid/datetime `default_factory`, an import-time pid/env/time default, a time- or DB-dependent computed var, or a build env that differs from the runtime env. Apps whose storage lives on small storage-only states are unaffected.

**Relation to thirdparty I-2** (a computed var's storage rewrite during hydration never reaches the browser). It is the complementary symptom of the same #7064 change:
* F1: the boot delta is accidentally written (too much is persisted).
* I-2: a deliberate write made during the boot snapshot is dropped. The snapshot plus `_clean()` happen in one event, and 0.9.12's separate `update_vars_internal` delta used to carry such writes.
* A fix should handle both together. Keeping `is_hydrated:false` in the root of the diffed boot delta fixes F1. On its own, though, that makes the boot delta never written, so I-2 needs a follow-up delta of storage vars that changed during hydration.
* Conversely, F1's accidental write can mask I-2 for states that are sent in full.

**Rerun:**
```
SB=...; V=$SB/apps/verify_hydration_0; mkdir -p $V/src $V/drivers $V/scripts $V/logs $V/results $V/run
cp -r verification/f1-client-storage-defaults/apps/{f1plain,f1combo} $V/src/
mkdir -p $V/src/v2 && cp -r verification/f1-client-storage-defaults/apps/f1combo_v2 $V/src/v2/f1combo
cp verification/scripts/* $V/scripts/; cp verification/f1-client-storage-defaults/drivers/* verification/f6-prenav-onload/drivers/* $V/drivers/
cp drivers/waitsrv.py drivers/prenav_test.py $V/drivers/      # explorer's helpers
NP="env NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1"; DRV=$SB/envs/driver/bin/python
$V/scripts/vsrv.sh start f1combo-alpha alpha prod $V/src/f1combo 3720 3720
$NP $DRV $V/drivers/waitsrv.py 580 http://localhost:3720/ http://localhost:3720/ping
$NP $DRV $V/drivers/f1_check.py http://localhost:3720/ - /tmp/v1.json out.json pl-ls,wu-ls,wu-sync,cs-ls,cu-ls,ws-ls,wt-ls
$V/scripts/vsrv.sh stop f1combo-alpha; $V/scripts/vsrv.sh start f1combo-alpha alpha prod $V/src/v2/f1combo 3720 3720   # "new release"
$NP $DRV $V/drivers/f1_check.py http://localhost:3720/ /tmp/v1.json - returning.json pl-ls,wu-ls,wu-sync,cs-ls,cu-ls,wt-ls
$NP $DRV $V/drivers/f1_sync_tabs.py http://localhost:3720/ sync.json 2500
# same with stable on 3721; f1plain the same way (ids theme,consent,tab)
```

### F6: behavior CONFIRMED; not a clean regression (pre-existing race, different symptom); low severity

**The explorer's driver reproduces** (`prenav_test.py`, 2 s `route_web_socket` hold, prod; `f6-prenav-onload/results/prenav_*.json`, `logs/hyd-*-1.hydtrace.log`):
* Alpha, 4/4: `slow_load run1 step1` runs, then `other_load#1`, and `#slow-progress-other=1` lands on `/other`. Also `item_load id=1` (`path=/items/1`), then `id=2`.
* 0.9.12: the new page's on_load runs twice in 3/4 runs and once in 1/4. The old page's on_load never runs.

**The mount-time auth claim is confirmed.**
* `state.js:703-708`: `bootAuth()` builds the boot event through `withRouterData`, which reads `locationRef.current` at call time (`:529-558`, `:534`).
* `:728`: it is assigned once as a value, `socket.current.auth = bootAuth(true)`.
* `ensureSocketConnected()` → `connect()` returns early when the socket exists (`:687-692`). `reconnect()` is a no-op while `wait_connect` (`:740-752`). Nothing refreshes `auth` before the CONNECT.
* The location effect (`:1284-1318`) dispatches `is_hydrated:false` and queues `on_load_internal` for the new route. That event is sent after the CONNECT.
* The bundled socket.io-client 4.8.4 evaluates a function-valued `auth` at `onopen()` (`.web/node_modules/socket.io-client/build/esm/socket.js:405-414`), so a lazy auth is possible.
* Caveat for the fix: a lazy auth alone would make both the boot chain and the queued navigation `on_load_internal` name the new page. That reintroduces 0.9.12's double run unless the redundant queued `on_load_internal` is dropped (or not queued before the first connect).

**Realism without the Playwright hold.**
* `drivers/upgrade_delay_proxy.py` delays only `GET /_event` websocket upgrades by D ms. HTML, JS and /ping are not delayed.
* The app was built with `REFLEX_API_URL` pointing at the proxy.
* `drivers/f6_natural.py` clicks `#nav-item2` 0 ms or 300 ms after React attached the link's props (a human-like reaction time). It timestamps the WebSocket open, the `40` CONNECT and the click in-page.
* "In window" means the CONNECT was sent after the click.

| D (upgrade delay) | alpha, click 0 ms | alpha, click 300 ms | 0.9.12, click 0 ms | 0.9.12, click 300 ms |
|---|---|---|---|---|
| 0 | 0/3 | 0/3 | 0/2 | 0/2 |
| 100 | 0/2 | 0/2 | n/a | n/a |
| 300 | 2/2 | 0/2 | 2/2 | 0/2 |
| 500 | 2/2 | 2/2 | 2/2 | 2/2 |
| 800 | 2/2 | 2/2 | n/a | n/a |

* **The smallest delay that triggers it is about 300 ms for an immediate (bot-speed) click, and about 500 ms for a click 300 ms after the page became interactive.**
* At D=0 the warm socket's CONNECT goes out at about 210–330 ms, before the link is even interactive (about 250–410 ms). Both versions have the same window. Load average was about 6 on 4 CPUs, so numbers are ±50 ms.
* Inside the window:
  * Alpha's CONNECT names `/items/1` and the trace is `item_load id=1`, then `id=2`. The backend sequence is identical to a user who clicks just after the CONNECT; only the timing differs: the left page's on_load runs, and its deltas land, after the user is on the new page.
  * 0.9.12 runs `item_load id=2` twice (5 of 6 in-window runs; once in the 6th).
* **Alpha-only, user-visible: a navigation hijack.** Start on `/redir` (on_load returns `rx.redirect("/other")`) and click `/items/2` at D=800.
  * Alpha, 2/2: trace `redirect_load, item_load id=2, other_load#1`, final URL **`/other`**. The user reached `/items/2`, its on_load ran, and then the stale redirect bounced them away.
  * 0.9.12, 2/2: `item_load id=2` twice, final URL `/items/2`.
  * At D=0 both versions redirect first and then honour the click, with final `/items/2`.
  * An auth-guard on_load on the page being left behaves the same way.

**Classification.**
* The race window (a client-side navigation between React interactivity and the CONNECT) is pre-existing, with the same thresholds on 0.9.12, and 0.9.12 already misbehaves in it (a double on_load of the new page, which is harmful for non-idempotent on_loads).
* Alpha trades that for the old page's on_load running late. Its first deltas land on the new page, and its redirect can hijack the navigation.
* This is a new symptom inside a pre-existing race, not a regression from correct behavior.
* Low severity: it needs a websocket accept at least 300–500 ms slower than the page becoming interactive (cold start, scale-from-zero, an overloaded backend or LB) plus a click inside that window. The final state is consistent apart from the redirect case.
* Worth fixing together with the 0.9.12 double run.
