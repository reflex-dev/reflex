# event_hotpath — reflex 0.9.11a1 pre-release testing (PR #7025, event-loop hot path)

Cluster: correctness under the five hot-path changes of PR #7025 (state attribute fast path, eager foreground task
start on 3.12+, interval-only computed-var expiry check, memoized route matching, inline socket.io handlers) plus an
A/B throughput measurement against reflex 0.9.10.post2.

Changelog line under test: "Trimmed the framework overhead around every event handler: the state fast-paths its own
bookkeeping attributes, foreground handler tasks start eagerly on Python 3.12+, the computed-var expiry check only
looks at interval vars, route matching is memoized per path, and socket.io handlers run inline. About 28% less CPU per
trivial event and 20% more events per second per worker under concurrent load." (#7025)

Everything below was produced with PyPI-installed packages only (no checkout install). Two agents worked on this
cluster; the second (this one) re-ran every check and produced all numbers in this file. Results from the first
(interrupted) attempt are kept under `logs_prev_attempt/` for reference only where noted.

## TL;DR

* No regression found in 0.9.11a1 vs 0.9.10.post2 for event ordering, yields/chains, background tasks + StateProxy,
  3-deep substate hierarchies, interval computed vars, route matching (150 static + dynamic + splat routes, query
  strings, fragments, encoded ids, `frontend_path`), slow handlers / ping / multi-client isolation, exceptions,
  malformed socket messages, 100-click hammer. Python 3.11 and 3.13 (eager start applies on 3.13 only), with and
  without a custom asyncio task factory.
* A/B bench (python-socketio client, `reflex run --backend-only`, dev granian, 1 worker, 3 interleaved rounds each):
  under 20 concurrent clients 0.9.11a1 delivers **+17% (py3.11) / +21% (py3.13) events/s** and **-14% / -16% worker
  CPU per event**; serial single-client throughput +12% on 3.11, flat on 3.13. All 36 bench runs ended with exact
  counters (no lost/duplicated increments). Whole-worker CPU per trivial event is ~0.93-1.0 ms on this box, so the
  "28% less CPU per trivial event" of the changelog refers to framework-internal CPU, not to the whole worker.
* Six **pre-existing** defects/anomalies surfaced (all reproduce identically on 0.9.10.post2, so not release
  blockers for 0.9.11a1, but worth tickets): see "Issues".

## Environment

* Machine shared with other agents (4 CPU / 15 GB); load average 0.7-1.4 during the bench (recorded per run).
* venvs (all PyPI): `$SB/envs/smoke` reflex 0.9.11a1 py3.11; `$SB/envs/hp313` reflex 0.9.11a1 py3.13 (from the
  first attempt, verified `reflex.__file__` + version); `$SB/envs/base0910` reflex 0.9.10.post2 py3.11;
  `$SB/envs/hp313_base` reflex 0.9.10.post2 py3.13 (created here: `uv venv --python 3.13` +
  `uv pip install reflex==0.9.10.post2`); `$SB/envs/driver` playwright + python-socketio.
* `SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad`, working dir
  `$SB/apps/event_hotpath`. Ports 3180-3199 / 8180-8199 only.
* App dirs: `hotpath_app` (smoke), `hotpath_app_313` (hp313), `hotpath_app_base` (base0910), `hotpath_app_313_base`
  (hp313_base) — byte-identical `hotpath_app/hotpath_app.py` (md5 4da70b1253…); `routes_app` / `routes_app_base`
  identical source (md5 63350ec919…). Only `apps/hotpath_app` and `apps/routes_app` are copied to the repo.

## Apps

`apps/hotpath_app/hotpath_app/hotpath_app.py` (pages: `/` counter+hammer, `/ordering`, `/hier`, `/interval`, `/slow`,
`/backend`, `/shadow`):

* `OrderingState`: async generator `multi_yield` (3 yields with `await asyncio.sleep`), **sync generator**
  `sync_multi_yield` (3 yields, no awaits), `chain` (returns a list of events across states), `yield_other`
  (`yield OtherState.bump()`), `yield_sleep_yield`, `click_a/click_b`, `fg_append`, background `bg_task` using
  `async with self`, `self.get_state(OtherState)`, `self.get_var_value(OtherState.other_val)`, `self.parent_state`;
  `record_task` (async handler that never suspends: records `asyncio.current_task().get_name()` — exercises the
  eager-start path on 3.12+). Every log entry carries a global monotonic sequence number so ordering is checked
  server-side, not only by arrival.
* `Root3 > Mid3 > Leaf3`: 3-deep substates, reads/writes via `self.parent_state.parent_state`, inherited-var
  writes, background task reading parents through the StateProxy and reading `self.dirty_vars`.
* `IntervalState(TimeMixin)`: `rx.var(interval=1)`, `rx.var(cache=True, interval=timedelta(seconds=1))`, a mixin-
  provided interval var, a plain `cache=True` var, module-level recompute counters exposed via a `cache=False` var,
  background task reading an interval var through the StateProxy; two `rx.ComponentState` `Clock` instances (one
  generated state class each) with an interval var.
* `SlowState`: `slow` (`await asyncio.sleep(5)`), `fast`, `boom` (raises), `boom_async` (raises before its first
  await — inside `Task(eager_start=True)` on 3.12+).
* `BackendState` (built with `type()`): backend vars `_hidden`, `_items`, optional `_get_was_touched` (the PR's own
  unit-test name, enabled with `HP_GWT=1`), reads `self._backend_vars`.
* `ShadowState`: public var named `get_state`; `ShadowDeltaState`: public var named `get_delta`.
* `CounterState.factory_info` reports python version and whether a custom task factory is installed;
  `HP_TASK_FACTORY=1` installs one via a lifespan task (eager start must then be skipped per the PR review round).

`apps/routes_app/routes_app/routes_app.py`: index + 150 generated static pages + `/item/[id]`, `/docs/[[...splat]]`,
`/posts/all/[x]` beside `/posts/[id]`, `/apple` and `/app` (prefix collisions with `frontend_path='/app'`), every page
with `on_load=RouteState.record` recording `router.page.path/raw_path/params` and `router.route_id` with a counter.
`HP_FRONTEND_PATH=/app` sets `rx.Config(frontend_path)`.

## How to rerun (from `$SB/apps/event_hotpath`, scripts in `scripts/`)

```
# helper scripts expect the layout above; LOGDIR defaults to logs3
scripts/run_pw.sh smoke hotpath_app 3180 8180 smoke                 # dev server + scripts/pw_hotpath.py (all pages)
scripts/run_pw.sh hp313 hotpath_app_313 3181 8181 hp313 --only ordering,slow,hammer
HP_TASK_FACTORY=1 scripts/run_pw.sh hp313 hotpath_app_313 3184 8184 hp313_factory --only ordering,hier,slow,hammer
HP_GWT=1 scripts/run_pw.sh smoke hotpath_app 3185 8185 smoke_gwt --only backend
scripts/run_routes.sh smoke routes_app 3186 8186 smoke_dev ''        # scripts/pw_routes.py
scripts/run_routes.sh smoke routes_app 3187 8187 smoke_dev_fp /app   # frontend_path=/app
scripts/run_routes.sh smoke routes_app 3189 8189 smoke_prod '' --env prod   # prod: ONE port for both
scripts/run_socket.sh hp313 hotpath_app_313 hp313                    # socket_slow_test.py + socket_malformed_test.py
scripts/run_ab.sh 3 smoke:hotpath_app:new311 base0910:hotpath_app_base:old311 hp313:hotpath_app_313:new313 hp313_base:hotpath_app_313_base:old313
$SB/envs/driver/bin/python scripts/ab_summary.py logs3              # aggregate ab_*.json
scripts/run_all_pw.sh; scripts/run_pass2.sh                          # the exact sequences used here
scripts/repro_nocompile.sh smoke hotpath_app 3194 8194 smoke         # issue 1 repro
cd /tmp && $SB/envs/smoke/bin/python $SB/apps/event_hotpath/scripts/probe_routes_offline.py   # issue 2 offline
cd /tmp && $SB/envs/smoke/bin/python $SB/apps/event_hotpath/scripts/probe_names.py            # issue 3 offline sweep
cd /tmp && $SB/envs/smoke/bin/python $SB/apps/event_hotpath/scripts/probe_names2.py --out out.jsonl
```

All browser runs go through `scripts/pwlib.py` (Chromium at `/opt/pw-browsers/chromium`, console/pageerror/failed-
request/4xx-5xx/dialog capture); every run directory has `results.json`, `console.json` and screenshots.
Set `NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1` for clients (the scripts do), never for servers.

## Results

### A/B throughput (logs/ab_*.json, logs/ab_summary.md, logs/ab_console.out)

Method: `reflex run --backend-only --backend-port 8180 --loglevel info` (dev mode, granian, one worker) per variant,
python-socketio client speaking the frontend's wire format (`/_event` namespace, `?token=`, `emit("event", {token,
name, payload, router_data})`, deltas come back as `event` messages with `delta[state_full_name][var + "_rx_state_"]`).
Per round: 2000 serial `CounterState.increment` events (wait for each delta), 20 clients x 100 events concurrently,
2000 pipelined events on one socket; 3 rounds, variants interleaved each round (new311, old311, new313, old313) to
cancel machine-load drift; server CPU from `/proc/<pid>/stat` for the whole process tree and per pid (the granian
worker is the only pid with non-zero CPU). Medians over 3 rounds:

| variant | mode | ev/s | p50 ms | p99 ms | worker CPU µs/event | RSS MB |
|---|---|---|---|---|---|---|
| new311 (0.9.11a1 py3.11) | serial_2000 | 869.5 | 1.10 | 1.79 | 985 | 115 |
| old311 (0.9.10.post2 py3.11) | serial_2000 | 777.8 | 1.13 | 4.17 | 1040 | 130 |
| new313 (0.9.11a1 py3.13) | serial_2000 | 949.1 | 1.01 | 1.60 | 935 | 117 |
| old313 (0.9.10.post2 py3.13) | serial_2000 | 957.4 | 1.01 | 1.51 | 980 | 132 |
| new311 | concurrent_20x100 | 1467.2 | 13.44 | 26.25 | 745 | 120 |
| old311 | concurrent_20x100 | 1253.4 | 15.57 | 28.91 | 865 | 135 |
| new313 | concurrent_20x100 | 1798.1 | 10.97 | 17.58 | 615 | 122 |
| old313 | concurrent_20x100 | 1486.2 | 13.40 | 20.17 | 735 | 137 |
| new311 | pipelined_2000 | 1111.3 | – | – | 985 | 119 |
| old311 | pipelined_2000 | 1026.5 | – | – | 1055 | 134 |
| new313 | pipelined_2000 | 1154.5 | – | – | 955 | 122 |
| old313 | pipelined_2000 | 1018.7 | – | – | 1060 | 137 |

new vs old: py3.11 concurrent +17.1% ev/s, p50 -13.7%, p99 -9.2%, worker CPU/event -13.9%; pipelined +8.3%, CPU -6.6%;
serial +11.8%, CPU -5.3%. py3.13 concurrent +21.0% ev/s, p50 -18.1%, p99 -12.8%, CPU/event -16.3%; pipelined +13.3%,
CPU -9.9%; serial -0.9% (noise), CPU -4.6%. Counters exact in all 36 runs. RSS ~15 MB lower on 0.9.11a1.
The bench is noisy (other agents' servers were running; per-run load average is in each JSON). Absolute CPU/event
(~1 ms) covers granian + engine.io + socket.io + reflex + JSON for one trivial event on a shared 4-CPU box.

### Browser end-to-end (logs/pw_hotpath_*/results.json, screenshots alongside)

`scripts/pw_hotpath.py` drives all pages of the hotpath app in Chromium. Pass 1 (`scripts/run_all_pw.sh`) ran the full
suite on four variants; because a leaked `.web/nocompile` (issue 1) made those four dev servers skip the frontend
compile, the two checks that need the buttons added in this attempt (`#sync_my`, `#rec_task`) hit
`ordering.EXC: waiting for locator("#sync_my")` there, and everything else ran against the frontend compiled from the
same source minus those two buttons. Pass 2 (`scripts/run_pass2.sh`) re-ran `ordering,interval,shadow` on all four
variants with a fresh compile.

| run (results dir) | reflex / python | entries | fail | what failed |
|---|---|---|---|---|
| pw_hotpath_smoke | 0.9.11a1 / 3.11 | 32 | 3 | ordering.EXC (issue 1 artifact), interval.no_recompute_within_interval (test flake: 1 s expiry boundary fell between the two pokes, counts +1 -- test since aligned to a fresh tick), shadow.var_named_get_delta (issue 3) |
| pw_hotpath_hp313 | 0.9.11a1 / 3.13 | 32 | 3 | same three |
| pw_hotpath_base | 0.9.10.post2 / 3.11 | 32 | 3 | same three |
| pw_hotpath_base313 | 0.9.10.post2 / 3.13 | 32 | 2 | ordering.EXC (issue 1 artifact), shadow.var_named_get_delta (issue 3); aligned interval test passed |
| pw_hotpath_hp313_factory (`HP_TASK_FACTORY=1`, fresh compile) | 0.9.11a1 / 3.13 | 26 | 0 | -- ; `factory_info` shows `installed: true, n: 1556, loop_factory: true` (all handler tasks went through the custom factory, eager start skipped as the PR says); includes ordering.sync_generator_multi_yield and ordering.current_task_in_nonsuspending_async_handler (`name=reflex_event|...record_task|<token>|<ts>`) |
| pw_hotpath_smoke_gwt (`HP_GWT=1`) | 0.9.11a1 / 3.11 | 4 | 0 | -- ; but see issue 5 (server log traceback at shutdown) |
| pw_hotpath_smoke2 (pass 2, fresh compile, `--only ordering,interval,shadow`) | 0.9.11a1 / 3.11 | 19 | 1 | shadow.var_named_get_delta (issue 3) — sync_generator_multi_yield, current_task probe and the aligned interval checks pass |
| pw_hotpath_hp3132 (pass 2) | 0.9.11a1 / 3.13 | 19 | 1 | shadow.var_named_get_delta |
| pw_hotpath_base2 (pass 2) | 0.9.10.post2 / 3.11 | 19 | 1 | shadow.var_named_get_delta |
| pw_hotpath_base3132 (pass 2) | 0.9.10.post2 / 3.13 | 19 | 1 | shadow.var_named_get_delta |

Checks (each on every variant above unless noted): ordering.multi_yield (3 progressive deltas in order),
ordering.chain_list_of_events (`chain-start < bump:from-chain < after-chain` by server sequence number),
ordering.yield_other_state_handler (yielded cross-state event round-trips via the client after the handler finishes),
ordering.yield_sleep_yield (3 deltas at +0.04/+0.42/+0.72 s), ordering.rapid_two_buttons (40 JS-synchronous clicks
alternating A/B in 20 patterns: server order == click order), ordering.background_interleave_stateproxy
(`bg-start, fg:1, fg:2, fg:3, bg-mid other_val=100 gvv=0 parent=State, bg-end`; `get_state`/`get_var_value`/
`parent_state` through the StateProxy), hier.* (3-deep reads/writes via `parent_state`, inherited-var writes, background
read incl. `dirty_vars=[]`), interval.* (no recompute within the interval for int / timedelta / mixin interval vars and
the plain cached var; after expiry only the three interval vars recompute (+1 each) and `cached_plain` +0; dependency
change recomputes `cached_plain` exactly once; StateProxy read in a background task sees a fresh value after 1.5 s;
two ComponentState clocks refresh independently on their own events), backend.* (backend vars read/write in place,
survive reload), shadow.var_named_get_state (works, pruned from `_fast_attr_names`), slow.* (other client's event
answered in 0.07 s while a 5 s handler runs; same client's 3 queued events apply after it in order; exception, async
exception before first await, two rapid exceptions: socket keeps working, `fast_count` exact), hammer.* (100 Playwright
clicks in 3.4 s, 100 JS-synchronous clicks, 100 async-no-await clicks, 100 mixed: `count=100` every time). Browser
console: no errors/warnings beyond the known-benign list in any run; no failed requests; no dialogs.

### Route matching (logs/pw_routes_*/results.json, visits.txt, ws_sent.json)

`scripts/pw_routes.py`: initial load, 14 client-side link navigations, the same 14 as direct loads (incl. `/item/1` then
`/item/2`, `/item/2?q=x&z=9#frag`, `/docs`, `/docs/a/b`, `/posts/all/7` vs `/posts/all` (-> `/posts/[id]`, id=all) vs
`/posts/42`, `/static-0`, `/static-149`, `/apple`, `/app`, revisit `/item/1`), direct-only `/item/a%20b` (id="a b"),
`/item/h%C3%A9llo` (id="héllo"), `/docs/x/y/z/`, `/item/100`..`/item/109`, trailing-slash `/item/5/` and
`/static-7/`, `/index`, then a final total `n_loads` check (every on_load counted exactly once: 47 == 47).

| run | reflex | frontend_path | pass | fail | anomaly |
|---|---|---|---|---|---|
| pw_routes_smoke_dev | 0.9.11a1 | '' | 44 | 1 (splat trailing '' — anomaly 6) | 1 (`/index`, issue 4) |
| pw_routes_smoke_dev_fp | 0.9.11a1 | /app | 40 | 5 (4 x issue 2 + anomaly 6) | 1 (issue 4) |
| pw_routes_base_dev_fp | 0.9.10.post2 | /app | 40 | 5 (identical) | 1 (identical) |
| logs_prev_attempt/pw_routes_{smoke_prod,smoke_prod_fp,base_dev} | 0.9.11a1 prod, 0.9.10.post2 dev | ''/'/app' | same pattern (first attempt, same app source, `--env prod` single port) |

Every dynamic route reports the right pattern (`router.page.path`), raw path, params and `route_id`; `/item/1` then
`/item/2` (same pattern, different path, memo hit vs miss) both correct; query and fragment preserved in `raw_path`
and merged into params (`q`, `z`); the client always sends the basename-relative pathname (ws_sent.json).

### Socket-level (logs/socket_slow_*.json, logs/socket_malformed_*.json, logs/socket_*.server.log)

python-socketio against `reflex run --backend-only` for hp313 (0.9.11a1/3.13), base313 (0.9.10.post2/3.13), smoke
(0.9.11a1/3.11): ping baseline 0.6-1.0 ms; **5 pings answered in 1.3-2.2 ms while the same socket's 5 s handler runs**
(inline handlers do not block the receive loop on ping); second client's event answered in ~3 ms during the slow
handler; same client's 3 queued events applied after `slow_done` in order (total 5.01 s); exception in a handler ->
next event answered in ~2 ms, ping fine. Malformed messages (19 checks: non-JSON string, JSON list, list, int, None,
{}, missing name, unknown handler, payload not a dict, extra payload arg, router_data not a dict / None, foreign
token, no token, extra fields, unknown socket event, event with no args, burst of 200 bad + 200 good interleaved,
final ping): all pass, counter exact, on all three variants. Server logs carry one traceback per bad message
(206 `EventDeserializationError`, plus KeyError/TypeError/AttributeError for the payload cases) — identical mix on
both versions; noisy but expected.

### Offline probes (no server)

* `scripts/probe_names.py` (95 cases: 19 framework names x {public var, backend var, event handler, plain method,
  computed var}) run under smoke / hp313 / base0910: **91/95 byte-identical outcomes between 0.9.11a1 and
  0.9.10.post2**; the remaining 4 differ only in memory addresses inside reprs. See issue 3 for what those outcomes
  are. Files: `logs_prev_attempt/probe_names_{smoke,hp313,base0910}.jsonl` (first attempt; re-summarised here).
* `scripts/probe_names2.py`: `_fast_attr_names` pruning for a subclass defining `get_state`, for a child inheriting
  it, for a backend var `_get_was_touched`, `setup_dynamic_args({"get_value": ...})` (class + substate),
  `add_var("get_delta", ...)` on a grandparent (3 levels pruned), `ComponentState.create()` twice (per-class
  `_interval_computed_var_names`), StateProxy-style `_expired_computed_vars`. All as the PR describes. Its
  `backend_var_gwt.ok=false` and `mixin_interval` error are probe bugs (expectation on `dirty_vars` after `_clean()`;
  an unannotated lambda computed var) — identical on base0910.
* `scripts/probe_routes_offline.py`: 61 (path, frontend_path) matches on the memoized matcher vs the 0.9.10.post2
  matcher — identical, including flipping `config.frontend_path` on the same router object (cache keyed on the
  prefix) and re-checking after 5000 distinct paths (lru maxsize 4096). `logs/routes_offline_{smoke,base0910}.jsonl`.

## Issues (all pre-existing: reproduced on 0.9.10.post2, regression=false)

### 1. `reflex run --backend-only` leaves `.web/nocompile` behind; the next full `reflex run` silently skips the frontend compile and serves a stale frontend

Mechanism (identical code in both versions): `reflex run --backend-only` calls `_skip_compile()` (sets
`REFLEX_SKIP_COMPILE`) and `exec.run_backend()` touches `.web/nocompile` for the worker. `App._should_compile()`
checks `REFLEX_SKIP_COMPILE` **before** the marker, so the worker never unlinks the marker. The next `reflex run`
(frontend + backend) hits the marker in the CLI's `_compile_app()` -> `_should_compile()` returns False and deletes
it -> no frontend compile at all; `run_backend` re-creates the marker and the worker consumes it. Vite serves whatever
`.web/app` already contained. Symptoms: newly added components/pages missing; if state names changed the browser shows
"Cannot process state update ... refreshing the page or clearing your browser cache" (seen in
`logs_prev_attempt/hotpath_smoke_dev_stalefrontend.log`).

Repro: `scripts/repro_nocompile.sh smoke hotpath_app 3194 8194 smoke` and `... base0910 hotpath_app_base 3195 8195 base0910`
(`logs/repro_nocompile_{smoke,base0910}.out`, server logs `logs/nocompile_*_{backendonly,fullrun,fullrun2}.log`), both
versions identical: step 1 `.web/nocompile` is present after the backend-only server stops (LEAK); step 2 delete
`.web/app/routes/[ordering]._index.jsx` and start a full `reflex run` -> the marker is consumed, no "Compiling" line,
the page is not regenerated and Vite dies with `Error: ENOENT: no such file or directory, open '.../.web/app/routes/
[...]._index.jsx'` / `script "dev" exited with code 1`; step 3 the same command again (no marker) -> "Compiling: 100%",
page regenerated, `/ordering` HTTP 200. In this campaign it turned every dev run that followed a
bench run into a stale-frontend run (the `ordering.EXC ... waiting for locator("#sync_my")` failures in the first-pass
`pw_hotpath_{smoke,hp313,base,base313}` results, and the missing `sync_my` in `.web/app/routes/[ordering]._index.jsx`);
pass 2 re-ran those pages after removing the marker. The first attempt's `logs_prev_attempt/hotpath_smoke_dev_stalefrontend.log`
shows the other symptom ("Cannot process state update ... clearing your browser cache").

### 2. With `rx.Config(frontend_path="/app")` the backend mis-routes any page whose route starts with the prefix text

The client sends the basename-relative pathname (`/apple`, `/app`); `route.get_route` strips `config.frontend_path`
again with `str.removeprefix`, so `/apple` -> `le` -> no match -> `router.page.path == "/404"`, and `/app` -> `` ->
`/` -> the index page's `on_load` runs and `router.route_id == "/index"`. Browser evidence:
`logs/pw_routes_smoke_dev_fp/results.json` (`routes.client_nav./apple ... WRONG ROUTE MATCH: /404`,
`routes.client_nav./app ... WRONG ROUTE MATCH: /index`, same for direct loads) and the identical
`logs/pw_routes_base_dev_fp/results.json` on 0.9.10.post2; offline: `routes_offline_*.jsonl` rows with `"fp": "/app"`.
Routes that do not start with the prefix text are matched correctly with the prefix, including
`/app/item/1`, `/app/static-3`, `/app/index`. Severity medium: wrong `on_load` fires / wrong `router_data` for such
pages; only apps whose `frontend_path` is a prefix of another route name are affected.

### 3. State attributes named like BaseState internals are not validated: some collide silently, others crash with cryptic errors

Only `get_delta/get_state/get_substate/get_value` as **event handlers** get a clear
`EventHandlerShadowsBuiltInStateMethodError`, and computed vars named `dirty_vars/dirty_substates/parent_state/
substates/router/_backend_vars/_was_touched` get `ComputedVarShadowsBaseVarsError`. Everything else is either a
cryptic failure or silent:
* public var `get_delta` (browser test `shadow.var_named_get_delta`, page `/shadow`): the handler runs but every
  event on that state dies in `get_delta()` with `TypeError: 'int' object is not callable` in the server log
  (`logs/hotpath_smoke.log`, `logs/hotpath_hp313.log`, `logs/hotpath_base.log`) — nothing reaches the browser,
  no toast, the UI just does not update. Same for vars named `get_value`, `_expired_computed_vars`, `_mark_dirty`
  (`'str' object is not callable` inside the framework), `get_fields/get_name/get_full_name/get_skip_vars/get_substate`
  (class creation fails with `TypeError: 'str' object is not callable` deep in state setup).
* public var `router` / `parent_state` / `_was_touched` / `_backend_vars`: class is created, reading the attribute
  returns the framework object (RouterData proxy, the parent State, ...), not the user's value; after assignment the
  user value is returned but never appears in any delta — silent.
* public var `dirty_vars` / `dirty_substates` / `substates`: assignment works, `get_delta()`/`dict()` then raise
  `AttributeError: 'str' object has no attribute 'update'/'union'/'values'`.
* `@rx.event` / plain method named `get_fields/get_name/get_full_name/get_skip_vars` (classmethods in BaseState):
  class creation fails with `TypeError: get_name() missing 1 required positional argument: 'self'`.
* Names that work correctly on both versions: public var `get_state` (browser test `shadow.var_named_get_state`),
  backend var `_get_was_touched` (`HP_GWT=1` run), backend vars with any `_`-prefixed framework name.
All identical on 0.9.10.post2 (`probe_names_*.jsonl`, 91/95 byte-identical, 4 differ by memory addresses only). The
PR's `_fast_attr_names` pruning behaves as described (the shadow test's `note` shows the pruned set); the defect is the
missing upfront validation, which predates the PR. Severity low/medium (developer-experience; silent in the browser).

### 4. Direct load of `/index` renders the 404 page while the backend runs the index page's `on_load`

`page.goto("/index")` -> React Router shows "404: Page not found" (`splat=['index']`), but the backend route
matcher maps `/index` -> `/` and fires `RouteState.record` with `route_id="/index"`, `path="/index"`. Both versions,
dev and prod (`logs/pw_routes_*/results.json`, entry `routes.direct_load./index`). Low severity; the frontend and
backend disagree about whether `/index` is a page.

### 5. A backend var named `_get_was_touched` breaks the disk state manager (`TypeError: 'int' object is not callable`)

`_get_was_touched` is the name PR #7025's own unit test uses for a colliding backend var, and reads/writes through the
state work (`pw_hotpath_smoke_gwt`, `backend.backend_var_named__get_was_touched` passes). But
`StateManagerDisk.set_state_for_substate -> token.get_and_reset_touched_state -> state._get_was_touched()` now calls
the user's int: traceback in `logs/hotpath_smoke_gwt.log` at shutdown (`_flush_write_queue`, "writing 3 remaining
items to disk" -> TypeError) and in the first attempt's `logs_prev_attempt/hotpath_base_gwt_dev.log` (0.9.10.post2,
identical). `scripts/repro_gwt_disk.sh` (backend-only server, one `bump_hidden` event, 7 s idle past the 2 s write debounce): **2 x "Error processing write queue: TypeError('int' object is not callable)" while running** — the periodic flush fails too, so the state is never persisted to disk while the app runs, then the same TypeError again in the shutdown flush — identical output for smoke (0.9.11a1) and base0910 (`logs/gwt_disk_{smoke,base0910}.log`, `logs/run_pass2.out`). Repro: `HP_GWT=1 scripts/run_pw.sh smoke hotpath_app 3185 8185 smoke_gwt --only backend`
then read the server log; or `scripts/repro_gwt_disk.sh smoke hotpath_app 8196 smoke`. Severity medium: silent loss
of state persistence for anyone who picks this name (dev mode default state manager is disk).

### 6. (anomaly) Optional catch-all with trailing slash yields an empty trailing splat segment

Direct load of `/docs/x/y/z/` -> `router.page.params == {'splat': ['x', 'y', 'z', '']}` (expected `['x','y','z']`);
`/docs/a/b` is fine. Both versions (`routes.direct_only./docs/x/y/z/` in pw_routes_smoke_dev, _fp and base_dev_fp).
Low severity.

## Benign / surprising observations (not issues)

* `[ERROR] Unexpected exit from worker-1` in the server log at shutdown when the process group receives SIGTERM
  (both versions, backend-only and full dev runs) — granian reporting the worker dying from the signal; benign.
* A sync generator handler's three yields arrive within one paint (`ordering.sync_generator_multi_yield` shows a
  single progressive state) whereas the async generator with `await asyncio.sleep` in between shows three — expected:
  nothing suspends between the sync yields.
* `slow.pre_exception_mutation_delivered` / `socket.pre_exception_mutation`: a mutation made before a handler raises
  is not delivered (boom_count stays 0 for a sync handler that raises after `self.boom_count += 1`); the exception is
  reported via the backend exception handler. Same in both versions.
* `interval.component_state_refresh_on_unrelated_event`: an expired interval var of a `ComponentState` is not
  refreshed by an event on an unrelated state (only dirty/related states are included in the delta) — by design, same
  on both versions.
* A var named `get_state` on a state prunes `get_state` from that class's `_fast_attr_names` (visible in the shadow
  page note); the framework method is still reachable on other states.
* Malformed socket messages (non-dict, missing name, unknown handler, wrong payload types, foreign token, no token):
  the socket survives, later events apply; the server takes the token from the socket session, so a message with a
  wrong/missing `token` field still applies to the connecting client's state (both versions).
* No `Task was destroyed`, `never awaited`, or eager_start-related lines in any server log (grep in every run
  script's "server log scan" section); all tracebacks in the hotpath logs are the intentional `boom` handlers plus the
  issue-3 `get_delta` TypeError (6 per full run).
* `DeprecationWarning: RouterData.page has been deprecated in version 0.8.1` is emitted by the routes app (it reads
  `self.router.page` on purpose to record `raw_path`/`params`).
