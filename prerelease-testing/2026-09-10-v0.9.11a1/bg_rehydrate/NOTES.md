# bg_rehydrate cluster — reflex 0.9.11a1 pre-release testing (2026-09-10)

Cluster: background-handler delta flush on exceptions (#6995), rehydrate after state eviction
under `StateManagerRedis` (#7072), backend-initiated events hitting expired state (#7073).

Everything below was run end-to-end with real `reflex run` servers (PyPI packages only:
`$SB/envs/smoke` = reflex 0.9.11a1 / reflex-base 0.9.11a1, `$SB/envs/base0910` = reflex 0.9.10.post2)
and a real headless Chromium driven by Playwright (`$SB/envs/driver`). The whole matrix was (re-)run
in one session between 18:06 and 18:30 on 2026-09-10 after a machine restart; a few evidence files
from an earlier pass on the same machine/versions (13:20-14:04) are kept and marked below.

`SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad`; this directory
in the repo is a copy of `$SB/apps/bg_rehydrate/` minus `.web/`, `.states/`, `__pycache__`.

## Layout

```
bgflush_app/            app for #6995 (custom backend_exception_handler, rx.var(cache=False), 7 bg handler variants,
                        page whose on_load is the raising handler; BGFLUSH_DEFAULT_HANDLER=1 uses the default handler)
rehydrate_app/          app for #7072/#7073 (pages /, /page-b, /item/[item_id], custom 404 with on_load,
                        LocalStorage + Cookie vars, second substate OtherState, backend API routes)
bgflush_app_base/       byte-identical copies used for the 0.9.10.post2 baseline runs (separate .web)
rehydrate_app_base/
scripts/serve.sh        start a server: serve.sh <venv> <appdir> <label> <FP> <BP> [--env prod]  (log -> logs/<label>.log)
scripts/stop.sh         stop it: stop.sh <label>
scripts/pwlib.py        Playwright helpers: console/pageerror/failed-request + websocket FRAME capture, delta parsing
scripts/pw_bgflush.py   driver for #6995 (17 checks)
scripts/pw_bgflush_default.py   #6995 with the DEFAULT backend exception handler (5 checks, reads the server log)
scripts/pw_rehydrate.py driver for #7072/#7073 + adjacent scenarios A..K, I, I2 (~45 checks)
scripts/pw_runaway_probe.py     #7073 runaway probe: one backend event on expired state, samples /api/runs for N s
scripts/pw_prod_multiworker.py  UI-only variant of A/B for a multi-worker prod server
scripts/pw_prod_crossworker.py  cross-worker delta delivery probe (backend enqueue x N, count deltas in the browser)
scripts/whoami_probe.py         hits /api/whoami N times: distinct worker pids vs token-manager instance_ids
logs/<label>.log        full server logs (dev: --loglevel debug); *_runaway_dev.trimmed.log is an excerpt
logs/pw_*/results.json  per-check results incl. the websocket deltas observed for each step
logs/pw_*/ws_frames.json, console.json, server_log_tail.json
shots/<label>/*.png     screenshots at key moments
```

Both apps mount extra HTTP routes through `rx.App(api_transformer=Starlette(...))`:

* bgflush: `GET /api/state` -> `{"beats": <# times the rx.var(cache=False) was computed>, "exc": [handled exceptions], "flush_fail": bool}`, `GET /api/reset`.
* rehydrate: `GET /api/runs` (module-level on_load run counters + log tail), `GET /api/reset`,
  `GET /api/enqueue?token=T&event=ping[&n=3][&wait=0]` (**backend-initiated event**: `Event.from_event_type(State.ping())[0]`
  passed to `app.event_processor.enqueue(token, event)` — no `router_data`),
  `GET /api/modify?token=T[&field=pings][&legacy=1]` (**backend change via `async with app.modify_state(rx.BaseStateToken(ident=T, cls=State))`**;
  `legacy=1` passes the bare client-token string instead), `GET /api/expire?token=T`,
  `GET /api/keys?token=T` (redis keys + TTL / in-memory keys), `GET /api/kick?token=T&mode=eio|sio`, `GET /api/whoami`.

The client token is read from `sessionStorage.token` in the browser. State expiry is
`REFLEX_REDIS_TOKEN_EXPIRATION=5` (seconds; also drives the memory/disk managers).

## Exact rerun commands

```bash
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
A=$SB/apps/bg_rehydrate        # or the copy in the repo, after adjusting SB/A at the top of scripts/serve.sh + stop.sh
export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1   # for the driver/curl ONLY (not for the servers)
PW=$SB/envs/driver/bin/python

# redis for the redis runs (port = BP 8220 + 15)
redis-server --port 8235 --save '' --daemonize no > $A/logs/redis_8235.log 2>&1 &

# ---- #6995 (bgflush) --------------------------------------------------------------
$A/scripts/serve.sh smoke    $A/bgflush_app      bgflush_smoke_dev 3220 8220
cd $A && $PW scripts/pw_bgflush.py --url http://localhost:3220 --api http://localhost:8220 \
     --out logs/pw_bgflush_smoke --shots shots/bgflush_smoke --label smoke
$A/scripts/stop.sh bgflush_smoke_dev
BGFLUSH_DEFAULT_HANDLER=1 $A/scripts/serve.sh smoke $A/bgflush_app bgflush_smoke_defaulthandler_dev 3220 8220
cd $A && $PW scripts/pw_bgflush_default.py --url http://localhost:3220 --api http://localhost:8220 \
     --log logs/bgflush_smoke_defaulthandler_dev.log --out logs/pw_bgflush_smoke_defaulthandler --shots shots/bgflush_smoke_defaulthandler
$A/scripts/stop.sh bgflush_smoke_defaulthandler_dev
$A/scripts/serve.sh base0910 $A/bgflush_app_base bgflush_base_dev 3224 8224   # baseline
cd $A && $PW scripts/pw_bgflush.py --url http://localhost:3224 --api http://localhost:8224 \
     --out logs/pw_bgflush_base --shots shots/bgflush_base --label base0910
$A/scripts/stop.sh bgflush_base_dev

# ---- #7072 / #7073 (rehydrate) ---------------------------------------------------
REFLEX_REDIS_URL=redis://localhost:8235 REFLEX_REDIS_TOKEN_EXPIRATION=5 \
  $A/scripts/serve.sh smoke $A/rehydrate_app rehydrate_smoke_redis_dev 3221 8221
cd $A && $PW scripts/pw_rehydrate.py --url http://localhost:3221 --api http://localhost:8221 --exp 5 \
     --out logs/pw_rehydrate_smoke_redis --shots shots/rehydrate_smoke_redis --label smoke_redis
$A/scripts/stop.sh rehydrate_smoke_redis_dev

REFLEX_STATE_MANAGER_MODE=memory REFLEX_REDIS_TOKEN_EXPIRATION=5 \
  $A/scripts/serve.sh smoke $A/rehydrate_app rehydrate_smoke_memory_dev 3222 8222
cd $A && $PW scripts/pw_rehydrate.py --url http://localhost:3222 --api http://localhost:8222 --exp 5 \
     --out logs/pw_rehydrate_smoke_memory --shots shots/rehydrate_smoke_memory --label smoke_memory \
     --touch $A/rehydrate_app/rehydrate_app/rehydrate_app.py          # --touch enables I2 (dev backend reload)
$A/scripts/stop.sh rehydrate_smoke_memory_dev

# dev default without redis = StateManagerDisk
REFLEX_REDIS_TOKEN_EXPIRATION=5 $A/scripts/serve.sh smoke $A/rehydrate_app rehydrate_smoke_disk_dev 3222 8222
cd $A && $PW scripts/pw_rehydrate.py --url http://localhost:3222 --api http://localhost:8222 --exp 5 \
     --out logs/pw_rehydrate_smoke_disk --shots shots/rehydrate_smoke_disk --label smoke_disk --skip reconnect
$A/scripts/stop.sh rehydrate_smoke_disk_dev

# prod mode (ONE port for both) + redis. prod defaults to 2*CPU+1 granian workers (9 here); the app's module-level
# counters are per process, so the full driver is run with ONE worker:
GRANIAN_WORKERS=1 REFLEX_REDIS_URL=redis://localhost:8235 REFLEX_REDIS_TOKEN_EXPIRATION=5 \
  $A/scripts/serve.sh smoke $A/rehydrate_app rehydrate_smoke_redis_prod_1w 3223 3223 --env prod
cd $A && $PW scripts/pw_rehydrate.py --url http://localhost:3223 --api http://localhost:3223 --exp 5 \
     --out logs/pw_rehydrate_smoke_redis_prod --shots shots/rehydrate_smoke_redis_prod --label smoke_redis_prod --skip reload
$A/scripts/stop.sh rehydrate_smoke_redis_prod_1w
# prod with the DEFAULT worker count (Issue 1 below):
REFLEX_REDIS_URL=redis://localhost:8235 REFLEX_REDIS_TOKEN_EXPIRATION=5 \
  $A/scripts/serve.sh smoke $A/rehydrate_app rehydrate_smoke_redis_prod_9w 3223 3223 --env prod
$PW $A/scripts/whoami_probe.py http://localhost:3223 60            # -> 9 pids, 1 instance_id
cd $A && $PW scripts/pw_prod_crossworker.py --url http://localhost:3223 --n 6 --out logs/pw_prod_crossworker_9w
cd $A && $PW scripts/pw_prod_multiworker.py --url http://localhost:3223 --exp 5 --out logs/pw_prod_multiworker_9w
$A/scripts/stop.sh rehydrate_smoke_redis_prod_9w

# baselines (0.9.10.post2)
REFLEX_REDIS_URL=redis://localhost:8235 REFLEX_REDIS_TOKEN_EXPIRATION=5 \
  $A/scripts/serve.sh base0910 $A/rehydrate_app_base rehydrate_base_redis_dev 3225 8225
cd $A && $PW scripts/pw_rehydrate.py --url http://localhost:3225 --api http://localhost:8225 --exp 5 \
     --out logs/pw_rehydrate_base_redis --shots shots/rehydrate_base_redis --label base_redis \
     --touch $A/rehydrate_app_base/rehydrate_app/rehydrate_app.py
$A/scripts/stop.sh rehydrate_base_redis_dev
# WARNING: on 0.9.10.post2 + memory manager ONE backend event on expired state triggers the #7073 runaway loop
# (backend pegged until the server is killed). Probe it for 6 s, kill, then run the rest on a fresh server:
REFLEX_STATE_MANAGER_MODE=memory REFLEX_REDIS_TOKEN_EXPIRATION=5 \
  $A/scripts/serve.sh base0910 $A/rehydrate_app_base rehydrate_base_memory_runaway_dev 3226 8226
cd $A && $PW scripts/pw_runaway_probe.py --url http://localhost:3226 --api http://localhost:8226 --exp 5 --sample 6 \
     --out logs/pw_runaway_base_memory --shots shots/runaway_base_memory
$A/scripts/stop.sh rehydrate_base_memory_runaway_dev
REFLEX_STATE_MANAGER_MODE=memory REFLEX_REDIS_TOKEN_EXPIRATION=5 \
  $A/scripts/serve.sh base0910 $A/rehydrate_app_base rehydrate_base_memory_dev 3226 8226
cd $A && $PW scripts/pw_rehydrate.py --url http://localhost:3226 --api http://localhost:8226 --exp 5 \
     --out logs/pw_rehydrate_base_memory --shots shots/rehydrate_base_memory --label base_memory \
     --skip backend_event unknown_token --touch $A/rehydrate_app_base/rehydrate_app/rehydrate_app.py
$A/scripts/stop.sh rehydrate_base_memory_dev
REFLEX_REDIS_URL=redis://localhost:8235 REFLEX_REDIS_TOKEN_EXPIRATION=5 \
  $A/scripts/serve.sh base0910 $A/rehydrate_app_base rehydrate_base_redis_prod_9w 3227 3227 --env prod
$PW $A/scripts/whoami_probe.py http://localhost:3227 60
redis-cli -p 8235 monitor > $A/logs/redis_monitor_crossworker_base_9w.log &   # optional evidence capture
cd $A && $PW scripts/pw_prod_crossworker.py --url http://localhost:3227 --n 6 --out logs/pw_prod_crossworker_base_9w
$A/scripts/stop.sh rehydrate_base_redis_prod_9w
redis-cli -p 8235 shutdown nosave
```

Manual repro of the runaway without the driver (0.9.10.post2, memory manager, token expiry 5 s):
open `http://localhost:3226/`, wait 8 s, read `sessionStorage.token` in devtools, then
`curl "http://localhost:8226/api/enqueue?token=<token>&wait=0"`; `curl http://localhost:8226/api/runs`
shows `index` climbing by ~300/s (`logs/pw_runaway_base_memory/samples.json`: 1842 runs in 6 s).

## Scenario map (pw_rehydrate.py) — result per configuration

| id | what | 0.9.11a1 redis-dev / memory / disk / redis-prod(1w) | 0.9.10.post2 redis | 0.9.10.post2 memory |
|----|------|-----------------------------------------------------|--------------------|---------------------|
| A  | #7073: page loaded, state expires, backend enqueues `ping` (no router_data): expect exactly 1 hydrate delta, no on_load run, `is_hydrated` ends true; 2nd/3rd backend event: no rehydrate; next routed click: on_load runs exactly once; a further click: no rehydrate | pass / pass / pass / pass | **fail**: no hydrate at all, `router_data` never restored, later routed click never re-runs on_load | **runaway**: `index` loader re-runs ~300/s, 585 hydrate deltas in 6 s, UI stuck at `hydrated=false`, backend pegged (`pw_runaway_probe.py`) |
| B  | #7072: on /page-b set LocalStorage+Cookie vars, click, bump OtherState; expire; click -> 1 hydrate delta, `load_b` re-runs (page-b=2), UI shows fresh state | pass / pass / n/a (disk reloads the pickle, no eviction) / pass | **fail** (no rehydrate; UI keeps stale values while the backend state is fresh) | pass (rehydrate path always worked for memory) |
| C  | dynamic route `/item/abc`: rehydrate re-runs the loader with `item_id=abc` | pass | fail (no rehydrate) | pass |
| D  | custom 404 with on_load: rehydrate runs the 404 loader exactly once more | pass | fail | pass |
| E  | click + immediate client-side navigation during rehydrate: consistent end state, no 404 loader, no errors | pass | pass | pass |
| F  | background task (12 s) running across expiry: finishes, writes fresh state (clicks=100); next click rehydrates + on_load once | pass | pass (no rehydrate on the click, but no error) | pass |
| G  | second tab opened via window.open (copied sessionStorage): server dedupes -> new token; tab1 rehydrate does not touch tab2; tab2 rehydrates its own page | pass | fail (no rehydrate in either tab) | pass |
| H  | backend event for a token nobody is connected with: hydrate once, ping runs, no loaders, no runaway | pass | pass (rehydrate bails entirely under redis) | **runaway** (same loop as A; skipped in the driver run) |
| J  | 3 routeless backend events enqueued back-to-back (`n=3&wait=0`) on expired state: exactly 1 hydrate delta, pings=3, no loaders; routed click afterwards runs on_load once | pass (all 4 configs) | fail (no hydrate) | (skipped: runaway) |
| K  | `async with app.modify_state(rx.BaseStateToken(ident=T, cls=State))` on expired state: no error, delta for the changed var only, no loaders, no runaway; next routed click rehydrates once | pass (memory / disk / redis-prod; redis-dev run predates the BaseStateToken fix, see anomaly 4) | pass | pass |
| I  | server closes the engine.io transport (`/api/kick`) after expiry | fail on both versions — anomaly 6 (socket.io client stack, not Reflex) | same | same |
| I2 | dev backend reload (touch app file) with the client connected: ws close/open, client re-sends hydrate + update_vars_internal + on_load_internal | pass (memory/disk: state lost & rebuilt) | pass (redis: state survives) | pass |

## Results: #6995 (bgflush)

0.9.11a1: 17/17 pass (`logs/pw_bgflush_smoke/results.json`, `logs/bgflush_smoke_dev.log`).
0.9.10.post2: 14/17 — the three failing checks are exactly the bug the changelog describes
(`noctx_raise_flushes_delta`, `yield_then_raise`, `noctx_raise_on_other`: the `rx.var(cache=False)` value on the page
did not refresh after a no-context background handler raised, i.e. no delta was flushed; `logs/pw_bgflush_base/results.json`).
Detail (0.9.11a1):

* bg handler that never enters `async with self`, mutates nothing, raises -> client receives 1 delta carrying the uncached var
  (`beat` +1) plus 1 events-only update; the custom `backend_exception_handler` receives `RuntimeError: boom-noctx` (not a flush
  error) and its `rx.toast.error` is rendered (`shots/bgflush_smoke/bgflush.noctx_raise_flushes_delta.png`).
* raises after `async with self` (mutation inside): count+1 and note reach the client from the context exit; exception handled;
  no double flush (1 delta + 1 events-only update).
* raises inside `async with self`: the mutation made before the raise IS flushed by `__aexit__` (count+1 visible), exception
  handled. Same on 0.9.10.post2.
* yields `rx.toast` then raises (no ctx): toast shown, delta flushed, exception handled.
* yields a state event (`State.bump_note`) then raises: yielded handler runs, beat refreshed, exception handled.
* flush itself fails (`beat` raises ValueError while the handler raised RuntimeError): handler gets the RuntimeError; the server
  log has `Error flushing delta after background handler State.bg_flush_fails raised:` followed by both chained tracebacks
  (`logs/bgflush_smoke_dev.log` lines 139-181). Not masked. On 0.9.10.post2 the flush never ran so there was nothing to mask.
* page whose `on_load` is the raising no-ctx bg handler (client-side nav and full reload): exception handled, `is_hydrated`
  still becomes true, page not stuck.
* same page under the DEFAULT backend exception handler (`BGFLUSH_DEFAULT_HANDLER=1`): beat refreshed, default
  `An error occurred. RuntimeError: boom-noctx` toast rendered, `[Reflex Backend Exception]` traceback logged once per raise,
  `Error flushing delta` logged once for the flush-fails variant (`logs/pw_bgflush_smoke_defaulthandler/`,
  `logs/bgflush_smoke_defaulthandler_dev.log`, `shots/bgflush_smoke_defaulthandler/`).
* No `Task exception was never retrieved` in any log of this cluster (grep over `logs/`), no other tracebacks; browser console
  clean in all bgflush runs.

## Results: #7072 / #7073 (rehydrate) on 0.9.11a1

* redis (dev): A..H, J pass; anomalies 1-3 below. One hydrate delta per rehydrate, on_load exactly once, `is_hydrated`
  false->true, no 404 loader runs, no tracebacks. `logs/pw_rehydrate_smoke_redis/`, `logs/rehydrate_smoke_redis_dev.log`.
* memory (dev, `REFLEX_STATE_MANAGER_MODE=memory`): A..H, J, K, I2 pass (39 checks); anomaly 1 reproduced; anomaly 2 does NOT
  happen (the hydrate covers all 7 substates). `logs/pw_rehydrate_smoke_memory/`.
* disk (dev default without redis): eviction from memory reloads the state from `.states/*.pkl` unless the pickle is older
  than the token expiration (mtime-based purge, writes are debounced 2 s), so B "survived" (clicks=2, no rehydrate) while
  A/J saw a fresh state and rehydrated correctly. Not a bug; dev-only. `logs/pw_rehydrate_smoke_disk/`.
* prod (redis, single port 3223, `GRANIAN_WORKERS=1`): A..H, J, K pass (36 checks), same anomalies as dev-redis;
  `logs/pw_rehydrate_smoke_redis_prod/`. With the default 9 workers see Issue 1.
* Log noise: without redis, a backend event for a never-connected token logs 3x
  `Warning: Attempting to send delta to disconnected client '<token>'` (hydrate, set_is_hydrated, ping deltas). With redis
  those go to the lost-and-found channel silently. Expected.

## Issue 1 (adjacent, pre-existing): cross-worker deltas are silently dropped in `reflex run --env prod` with the default worker count

Setup: `reflex run --env prod` with redis (`REFLEX_REDIS_URL`), default `GRANIAN_WORKERS` (2*CPU+1 = 9 here).
`scripts/whoami_probe.py` shows **9 distinct worker pids but a single `RedisTokenManager.instance_id`**
(`logs/whoami_smoke_prod_9w.txt`, `logs/whoami_base_prod_9w.txt`). `instance_id` is generated in `TokenManager.__init__`
when `rx.App()` is constructed; `reflex/reflex.py::_run_prod` compiles (imports) the app in the CLI process before
`exec.run_granian_backend_prod` calls `Granian(...).serve()` in that same process, so every forked worker inherits the same
`app` object and the same id. (Granian also warns `Configured number of workers appears to be higher than the amount of CPU
cores available` on this 4-CPU box — both versions.)

Consequence (`scripts/pw_prod_crossworker.py`, `logs/pw_prod_crossworker_9w/`, `logs/pw_prod_crossworker_base_9w/`,
`logs/redis_monitor_crossworker_base_9w.log`): a backend-initiated event (`app.event_processor.enqueue` from an API route,
i.e. exactly the #7073 path — the same holds for `app.modify_state()` outside the socket's worker) that lands on a worker
other than the one holding the websocket is processed (state in redis updates), but its delta never reaches the browser:
**0/6 deliveries on 0.9.11a1 and 0/6 on 0.9.10.post2**. The redis MONITOR capture shows the non-owner worker `GET`s
`token_manager_socket_record_<token>` (7 GETs) and then issues **no `PUBLISH`** (0): `RedisTokenManager._fetch_socket_record`
sees `record.instance_id == self.instance_id` with a sid it does not know and treats the record as its own stale socket ->
`_get_token_owner` returns None -> `emit_lost_and_found` returns False -> `EventNamespace.emit_update` drops the update with
no log line. The #7073 routeless hydrate is therefore also lost in this deployment: `pw_prod_multiworker.py` enqueued 3 backend
events after expiry and the browser saw the hydrate + `pings=1` only for the one that happened to land on the owner worker
(`logs/pw_prod_multiworker_9w/results.json`). The page only catches up on its next own event (which then rehydrates again).
With `GRANIAN_WORKERS=1` everything is delivered; the #7072/#7073 fixes themselves are correct.
**Identical on 0.9.10.post2 -> regression=false**, but it silently defeats the feature this cluster fixes in the default prod
configuration. Severity: high (silent loss of updates), not a 0.9.11 regression.

Repro without the driver: start the 9-worker prod server as above, open `/` in a browser, read `sessionStorage.token`, run
`curl "http://localhost:3223/api/enqueue?token=<tok>&event=ping&wait=1"` a few times: the page's `pings=` text stays 0
although `/api/runs` (from whichever worker answers) shows pings ran; after a click on the page the value jumps to the real count.

Related redis-only observation: `StateManagerRedis` sets a per-key TTL only on the substates it writes, so an idle ROOT
state key expires while a frequently written substate stays alive; the next event then rehydrates (hydrate delta +
`is_hydrated` toggle) although the user's data never left redis. Harmless with the default 1 h expiration; pre-existing.

## Anomalies / observations (none are release blockers; all regression=false)

1. **Client-storage vars are not re-synced after a backend-initiated rehydrate** (redis & memory & prod, 0.9.11a1 AND
   0.9.10.post2-memory). `State.hydrate` calls `_reset_client_storage()` and emits the full dict with `is_hydrated=False`; the
   frontend deliberately skips writing client storage for that delta, so the browser keeps `localStorage.rh_name='alice'` /
   cookie `rh_flavor=mint`, but the UI (and the backend) now show `name=''`, `flavor=''` until a full page reload (which
   re-sends `update_vars_internal`). Screenshot `shots/rehydrate_smoke_redis/B1_after_eviction_click.png` (the inputs still show
   alice/mint because they are uncontrolled; the bound texts are empty). Pre-existing behaviour of the rehydrate path (identical
   on 0.9.10.post2 with the memory manager); under redis on 0.9.10.post2 the UI simply stayed stale everywhere, so the new
   behaviour is strictly better but still surprising. Suggest the frontend re-send `update_vars_internal` when it receives a
   hydrate delta it did not request.
2. **Under redis the compatibility hydrate only covers the event's own substate chain.** `hydrate` emits `self.dict()` of the
   tree `StateManagerRedis` materialised (root + the event's substate: 2 substates vs 7 with the memory manager). A second,
   unrelated substate (`OtherState`) keeps its stale UI value (`other_count=1`) while the backend copy is fresh (0); the next
   `bump_other` then shows 1 again (0+1) instead of 2 — a visible "counter went backwards". Memory manager resets it
   correctly. Low severity; the same stale display exists on 0.9.10.post2 (which never rehydrated under redis at all), so
   regression=false. Evidence: `logs/pw_rehydrate_smoke_redis/results.json` -> `B.other_substate_after_rehydrate`
   (substates in hydrate delta = [2]) vs `logs/pw_rehydrate_smoke_memory/results.json` ([7]).
3. **After a routeless rehydrate the page shows reset on_load-derived values** (`loaded_page=''`, `load_seq=0`, `path=''`)
   until the client's next routed event, which then rehydrates a second time and re-runs the page's `on_load`
   (`J.ui_after_routeless_rehydrate`, `shots/rehydrate_smoke_redis/J_concurrent_backend_events.png`). This is what #7073
   designed ("no page to load, but hydration still has to finish"); worth a sentence in the docs for people who enqueue events
   from the backend: the client sees defaults until it acts. Pre-#7073 the page kept stale values instead (redis) or looped (memory).
4. **Confusing error for the deprecated string token in `app.modify_state`.** Passing the bare client token
   (`app.modify_state("<uuid>")`, still accepted with a `DeprecationWarning: Passing a string to modify_state has been
   deprecated in version 0.9.0`) fails with `ValueError: Invalid path: ('',)` because `BaseStateToken.from_legacy_token` expects
   the legacy `"<token>_<state full name>"` form and splits off an empty state name. Same result on 0.9.10.post2 (checked the
   pure function in both venvs; `App.modify_state` is byte-identical in both installs). Low; a clearer message ("legacy token
   must be `<client_token>_<state name>`; pass rx.BaseStateToken") would help. Evidence: `logs/rehydrate_smoke_redis_dev.log`
   line 141 and `logs/pw_rehydrate_smoke_redis/results.json` -> `K.modify_state_on_expired_state` (that run used the bare token;
   the API was then switched to `rx.BaseStateToken(ident=token, cls=State)`, which yields the ROOT state on both versions —
   navigate with `await state.get_state(State)` — and K passes in every later run).
5. Baseline runaway detail (0.9.10.post2 memory): the loop runs the **index** loader (not the 404 loader) for `path=` because
   `app.get_load_events("")` resolves the empty route to `/`; each iteration also emits a full hydrate delta (585 in 6 s), the
   client drops to `hydrated=false` (`shots/runaway_base_memory/runaway_probe.png`), the log fills with
   `Attempting to send delta to disconnected client` warnings (186 in ~8 s), and killing the server surfaces two
   `[Reflex Backend Exception] ... QueueShutDown: Event processor is not running, call .start(...) first.` tracebacks from the
   still-running chain (`logs/rehydrate_base_memory_runaway_dev.trimmed.log`, `logs/pw_runaway_base_memory/samples.json`).
   0.9.11a1 shows none of this.
6. **Server-side engine.io close is not noticed by the client.** `/api/kick?mode=eio` (`server.eio.disconnect(eio_sid)`) makes
   the client receive the engine.io CLOSE packet but Chromium reports no websocket close, the client never reconnects and its
   next click is written into the dead socket with no feedback. Same on 0.9.10.post2. Reflex itself never calls this API so
   this is an observation about the socket.io client stack rather than a Reflex bug; a real backend restart (I2) reconnects
   fine (`ws=['close','open',...]`, client re-sends hydrate/update_vars_internal/on_load_internal).
7. After a dev backend reload (I2) the console shows 2x `WebSocket connection ... failed: net::ERR_CONNECTION_REFUSED` while
   the backend is down — expected.
8. Prod-only: the console shows `Failed to load resource: 404` for (a) `/favicon.ico` (this app ships none), (b) `/nope`
   (custom 404 page served with HTTP 404 — expected) and (c) **the dynamic route `/item/abc`**: the static server answers
   HTTP 404 (SPA fallback) although the page then renders correctly client-side. Also prod-only: a full page load of `/page-b`
   is redirected (307) to `/page-b/`, so `self.router.url.path` is `/page-b/` after a full load but `/page-b` after client-side
   navigation (dev: always `/page-b`). Identical status codes on 0.9.10.post2 (`logs/smoke_prod_status_codes.txt`,
   `logs/base_prod_status_codes.txt`), so pre-existing static-hosting behaviour; noted because route-keyed logic that compares
   `router.url.path` literally sees two spellings in prod.
9. `DeprecationWarning: Implicit Radix Themes enablement ...` appeared on first start until `rx.plugins.RadixThemesPlugin()`
   was added to rxconfig — expected app-config deprecation, not a finding.

Evidence kept from the earlier pass of this cluster (13:20-14:04, same machine and package versions):
`logs/pw_prod_crossworker_9w_monitored/`, `logs/pw_prod_crossworker_9w_run2/`, `logs/redis_monitor_crossworker.log`
(0.9.11a1 redis MONITOR during the cross-worker probe), `logs/rehydrate_smoke_redis_prod_9w_run1.log`,
`logs/rehydrate_base_redis_prod_1w.log`, `logs/base_memory_runaway_runs.json`, `logs/base_prod_status_codes.txt`.
Everything else was regenerated in the 18:06-18:30 session.

## Process hygiene

All servers were started through `scripts/serve.sh` (pid files in `logs/*.pid`) and stopped with `scripts/stop.sh`;
redis ran on port 8235 (`logs/redis_8235.log`) and was shut down at the end.
`ps aux | grep -E 'reflex|granian|vite|bun|chrom|redis'` was empty of this cluster's processes before finishing.
