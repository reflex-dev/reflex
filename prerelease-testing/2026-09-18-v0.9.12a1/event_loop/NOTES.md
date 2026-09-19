# Cluster `event_loop` — reflex 0.9.12a1 pre-release testing

Scope: `@rx.var(cache=False)` delta dedupe (#6946), `supersedes=True` root-generation
ordering (#7168), deep self-chain `RecursionError` (#7145), callback event routing
(#7156 / #7157 + sonner 0.9.4a1), long-lived redis client for `/_health` (#7187).

Everything below was run from published PyPI packages only. Nothing was installed from
the `/home/user/reflex` checkout.

## Resolved versions

`uv pip freeze --python $SB/envs/shared/bin/python | grep -i reflex` (the under-test env):

```
reflex==0.9.12a1
reflex-base==0.9.12a1
reflex-components-code==0.9.6a1
reflex-components-core==0.9.10a1
reflex-components-dataeditor==0.9.3a1
reflex-components-gridjs==0.9.2a1
reflex-components-lucide==1.0.4
reflex-components-markdown==0.9.4a1
reflex-components-moment==0.9.4
reflex-components-plotly==0.9.7a1
reflex-components-radix==0.9.10a1
reflex-components-react-player==0.9.2
reflex-components-recharts==0.9.4a1
reflex-components-sonner==0.9.4a1
reflex-hosting-cli==0.1.72
```

Baseline env (`$SB/envs/prev`): `reflex==0.9.11.post1`, `reflex-base==0.9.11.post1`,
`reflex-components-core==0.9.9`, `-radix==0.9.9`, `-sonner==0.9.3`, `-recharts==0.9.3`,
`-markdown==0.9.3`, `-plotly==0.9.6`, `-code==0.9.5`, `-dataeditor==0.9.2`, `-gridjs==0.9.1`.

## The app

`elapp/` is one reflex app with six pages, each targeting one change:

| route | what it exercises |
| --- | --- |
| `/uncached` | 9 `@rx.var(cache=False)` vars: constant, derived, A→B→A alternating, `float('nan')`, freshly-rebuilt equal list, dict with differing key **order**, async uncached var, an uncached var on a **substate** reading the parent's base var, and one returning a non-serializable value (`complex`) |
| `/supersede` | `@rx.event(supersedes=True, background=True)` reached as two roots, as a child of two distinct root chains, as sibling fan-out, as a self-chaining poll loop with mid-run restart, and from a deliberately slow *stale* chain; plus foreground (`supersedes=True`, non-background) variants |
| `/recursion` | `on_load` → self-chaining `yield State.tick` for 3000 iterations, plus the same loop under a `supersedes=True` root; navigation away/back and reload mid-loop |
| `/callback` | toast `action`/`cancel` `on_click` fired from a frontend trigger, from the backend, inside `@rx.memo`, inside `rx.ComponentState`; `rx.call_script(callback=...)` to a State handler and to `State.handler(rx.upload_files(...))`; two upload zones (`u1` with `on_drop`, `u2` deferred) |
| `/filtered` | a downstream-style `BaseState.get_delta` monkeypatch (the pattern the `get_delta` docstring documents) that removes an uncached var's key from the delta |
| `/other` | navigation target |

Driver scripts live in `scripts/`. `wsdrive.py` is a shared harness capturing console
messages, page errors, failed requests, HTTP >= 400 and **every websocket frame**;
`analyze.py` turns a frame dump into per-delta key lists + byte totals.

## Exact rerun commands

```bash
SB=/tmp/claude-0/-home-user-reflex/4bc251b7-1728-51b6-97f5-dc5c7f35130a/scratchpad   # any scratch dir works

# --- env under test (PyPI only; NAME the component alphas explicitly) ---
cd $SB && uv venv $SB/envs/el --python 3.11
uv pip install --python $SB/envs/el/bin/python --prerelease=allow \
  'reflex==0.9.12a1' 'reflex-components-core==0.9.10a1' 'reflex-components-radix==0.9.10a1' \
  'reflex-components-sonner==0.9.4a1' 'reflex-components-code==0.9.6a1' \
  'reflex-components-dataeditor==0.9.3a1' 'reflex-components-gridjs==0.9.2a1' \
  'reflex-components-markdown==0.9.4a1' 'reflex-components-plotly==0.9.7a1' \
  'reflex-components-recharts==0.9.4a1'

# --- app ---
mkdir -p $SB/apps/event_loop/elapp && cd $SB/apps/event_loop/elapp
REFLEX_TELEMETRY_ENABLED=false $SB/envs/el/bin/reflex init --template blank
cp <this dir>/elapp/elapp/elapp.py $SB/apps/event_loop/elapp/elapp/elapp.py

# --- dev run (ports 3180/8180) ---
REFLEX_TELEMETRY_ENABLED=false $SB/envs/el/bin/reflex run \
  --frontend-port 3180 --backend-port 8180 --loglevel debug > dev.log 2>&1 &

# --- drive it (driver venv has playwright 1.63) ---
cd <this dir>/scripts
export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 PYTHONPATH=.
$SB/envs/driver/bin/python s_uncached.py  http://localhost:3180 ./out
$SB/envs/driver/bin/python s_supersede.py http://localhost:3180 ./out
$SB/envs/driver/bin/python s_recursion.py http://localhost:3180 ./out
$SB/envs/driver/bin/python s_callback.py  http://localhost:3180 ./out
$SB/envs/driver/bin/python s_filtered.py  http://localhost:3180 ./out
python3 analyze.py ./out/uncached.frames.jsonl     # delta keys + byte totals

# --- prod + redis (ONE port for both flags) ---
redis-server --port 8195 --save '' &
REFLEX_TELEMETRY_ENABLED=false REFLEX_REDIS_URL=redis://localhost:8195 \
  $SB/envs/el/bin/reflex run --env prod --frontend-port 3190 --backend-port 3190 \
  --loglevel debug > prod.log 2>&1 &
# /_health probe accounting
redis-cli -p 8195 CLIENT LIST | wc -l; redis-cli -p 8195 INFO stats | grep total_connections_received
for i in $(seq 1 300); do curl -s --noproxy '*' -o /dev/null http://localhost:3190/_health; done
redis-cli -p 8195 CLIENT LIST | wc -l; redis-cli -p 8195 INFO stats | grep total_connections_received

# --- baseline (0.9.11.post1): same app, module renamed elapp_prev/elapp_prev.py ---
$SB/envs/prev/bin/reflex run --frontend-port 3181 --backend-port 8181 ...
```

## Results

### #6946 uncached-var delta dedupe — WORKS, with one real defect (ISSUE-1)

Frame evidence: `out/uncached.frames.jsonl` (0.9.12a1) vs `out_prev/uncached.frames.jsonl`
(0.9.11.post1), same scenario, same clicks.

| | 0.9.11.post1 | 0.9.12a1 |
| --- | --- | --- |
| inbound websocket bytes | 26 059 | 15 274 |
| delta frames | 27 (25 555 B) | 24 (14 770 B) |
| `do_nothing` event (no var changes) | full 2 164 B delta | **no delta frame at all** |
| unrelated var bump (`nonce`) | 2 164 B, all 9 uncached vars | 98 B, `nonce` only |

The perf claim holds: about a **42 % reduction** in inbound bytes for this workload, and
events that change nothing now produce no frame.

Per-var behaviour on 0.9.12a1 (from the frames):

- constant `str`, freshly-rebuilt equal `list[int]`, `float('nan')`: sent once on hydrate,
  never re-sent. NaN dedupes correctly (it is keyed by its serialized form `NaN`, not by
  `==`), so the "NaN is never equal to itself" trap is handled.
- `u_alt` (A→B→A) and `u_derived` (changes every 3 bumps) appear only on the events where
  the value actually changes, **including** when the value returns to an earlier value
  (`reset` from counter=6 → `u_derived` d2→d0 and `u_async` as1→as0 were both re-sent;
  `u_alt` was 'A' at both 6 and 0 and was correctly omitted).
- async uncached var (`_drop_unchanged_delta_value` path) dedupes identically.
- uncached var on a **substate** reading a parent base var works.
- dict with **the same contents but different key order** is re-sent on every event.
  Expected given the digest-of-JSON key, but worth documenting: `{"a":1,"b":2}` vs
  `{"b":2,"a":1}` defeats the dedupe.
- per-client memory is correct: a second browser **context** (own sessionStorage token)
  got all uncached vars on its own hydrate and on its own first event; the two clients
  never shorted each other out.
- hard reload (same sessionStorage token) is safe because `State.hydrate` sends
  `self.dict()`, not `get_delta()`, so the whole state goes out regardless of the memo.
- prod + redis + 9 granian workers: identical, no missed update. The memo is visible in
  redis as `__last_delta_<var>_rx_state_` → `(token, key)` (`out_prod/redis_last_delta.txt`).

**ISSUE-1 (regression, high).** The memo is written where the value is *computed*
(`BaseState.get_delta` → `ComputedVar._record_delta_value`), not where the delta is
*delivered*. Any downstream `get_delta` wrapper that removes an entry — the monkeypatch
pattern the `get_delta` docstring itself documents ("the method is monkeypatched downstream
with a signature accepting only `self`"), which is what reflex-enterprise does — makes that
value unreachable forever: it is recorded as sent, the client never receives it, and it is
only re-sent when the value changes *again*.

`reflex/state.py` has `_suppress_delta_recording()` for exactly this hazard, but it is only
applied in `reflex/istate/shared.py:122`; a downstream filter has no way to reach it.

Repro (`scripts/s_filtered.py`, page `/filtered`), observed values vs baseline:

| step | 0.9.11.post1 | 0.9.12a1 |
| --- | --- | --- |
| load | `secret-0` | `secret-0` |
| bump while hidden (filter drops the key) | `secret-0` | `secret-0` |
| **show** (filter stops dropping) | **`secret-1`** | **`secret-0`** (stale) |
| bump (n=2) | `secret-2` | `secret-2` (n=1 never seen) |
| hide, bump (n=3), show | **`secret-3`** | **`secret-2`** (stale) |

Evidence: `out/filtered.txt`, `out_prod/filtered.txt`, `out_prev/filtered.txt`,
`screenshots/dev_filtered_after_show.png`, `screenshots/prod_filtered_after_show.png`.
Reproduces in dev (memory) and prod (redis, 9 workers) alike. This is the pure-reflex
confirmation of the `ent_mcp_oidc` cluster's ISSUE-2 handover.

### #7168 supersedes ordering — ALL CASES PASS, and the baseline shows what was fixed

`scripts/s_supersede.py`, markers appended by each invocation. `X:CANCELLED` means the
invocation's `asyncio.sleep` raised `CancelledError`.

| case | 0.9.11.post1 | 0.9.12a1 dev | verdict |
| --- | --- | --- | --- |
| two roots of the same superseding handler | `A:start, A:CANCELLED, B:start, B:done` | same | unchanged, correct |
| **shared superseding child under two different root chains** (#7041) | `chainA:root, cA:start, chainB:root, cB:start, cA:done, cB:done` — stale invocation kept running | `chainA:root, cA:start, chainB:root, cA:CANCELLED, cB:start, cB:done` | **FIXED** |
| sibling fan-out `return [refresh("x"), refresh("y")]` | both run | both run | correct (same generation coexists) |
| self-chaining poll loop, restarted mid-run | 12 ticks — the old loop kept running alongside the new one | 8 ticks — old loop cancelled, new loop continues | **FIXED** |
| **stale chain enqueues the handler after a newer chain already did** | `slow:root, B:start, slow:enqueue, stale:start, B:done, stale:done` — stale work ran | `slow:root, B:start, slow:enqueue, B:done` — stale invocation **dropped**, newer work untouched | **FIXED** |
| foreground (`supersedes=True`, not background) | `FA:start, FA:CANCELLED, FB:start, FB:done` | same | correct |
| different superseding handlers do not interfere | `FA:start, FA:done, B:start, B:done` | same | correct |
| two browser contexts (two tokens) | isolated | isolated | correct |

Prod + redis reproduces every case identically **except** the foreground one — see ISSUE-3.

### #7145 deep self-chain — NO RecursionError

`scripts/s_recursion.py`. The `on_load` self-chain ran the full 3000 iterations in ~11 s
(steady ~285 iterations/s, no visible slowdown across the run). A second 3000-iteration
loop under a `supersedes=True` root ran while the client navigated away client-side,
navigated back, restarted the root mid-run, and hard-reloaded the tab.

`grep -cE "RecursionError|Exception in callback|Traceback"` over the dev, prod and baseline
server logs: **0** in all three. No browser console errors, no page errors, no failed
requests. `screenshots/dev_recursion_loop_done.png`.

### #7156 / #7157 callback routing — FIXED for state and client events, still broken for uploads

`scripts/s_callback.py`, ten cases. Key comparison:

| case | 0.9.11.post1 | 0.9.12a1 |
| --- | --- | --- |
| frontend-fired toast, `action.on_click = State.handler` | `PAGEERROR queueEvents is not defined`, handler never ran | works |
| frontend-fired toast, `cancel.on_click = State.handler` | same error | works |
| frontend-fired toast, `on_click = rx.call_script(...)` | same error | works (`window.__alerted === true`) |
| toast inside `@rx.memo` (action + cancel) | same error | works |
| toast inside `rx.ComponentState` (action → `cls.hit`, cancel → `rx.set_clipboard`) | same error | works |
| backend-yielded toast, action/cancel → State handler | already worked | works |
| `rx.call_script(..., callback=State.handler)` | works | works |
| **any of the above where `on_click = State.handler(rx.upload_files(upload_id=...))`** | `queueEvents`/`filesById` error, upload never ran | **`ReferenceError: filesById is not defined`, upload still never runs** — see ISSUE-2 |
| plain `rx.upload(on_drop=...)` drop | works | works |

Verified identical in dev and prod (`out/callback.txt`, `out_prod/callback.txt`,
`out_prev/callback.txt`, `screenshots/*_callback_fe_toast.png`).

**ISSUE-2 (pre-existing, not a regression, high).** #7156's changelog line promises that
"a toast action triggering an upload handler" now works. The handler slot *is* now correct
— the compiled call is `ReflexEvent("…handle_upload", {...}, {}, "uploadFiles")`, handler
fourth — but the payload the same spec emits is `files: filesById?.["u2"]`, and
`filesById` only exists in the component that renders the `rx.upload`
(`const [filesById, setFilesById] = useContext(UploadFilesContext);`). In a toast callback
or an eval'd `rx.call_script` callback that binding is not in scope, so the click throws and
the upload never starts. Details and exact compiled JS under ISSUE-2 below.

### #7187 long-lived redis client for `/_health` — VERIFIED

prod, 9-10 granian workers, redis on 8195:

| | `CLIENT LIST` rows | `total_connections_received` |
| --- | --- | --- |
| before any probe | 1 | 4 |
| after 300 `/_health` probes | 10 | 15 |
| after 300 more | 10 | 17 |

One connection per worker, then flat. `/_health` returns `{"status":true,"redis":true}`.
600 probes cost 13 connections total, i.e. the per-probe connect/close is gone.

## Issues

### ISSUE-1 — uncached var filtered out of a delta by a downstream `get_delta` is never re-sent

- Severity: **high**. Regression vs 0.9.11.post1: **yes** (baseline delivers the value).
- Root cause (release source): `reflex/state.py` `BaseState.get_delta` calls
  `cvar._record_delta_value(self, value, token)` (line ~2385) while *building* the delta;
  `ComputedVar._record_delta_value`
  (`packages/reflex-base/src/reflex_base/vars/base.py:2689`) writes
  `instance.__last_delta_<js_expr> = (token, key)` immediately. Nothing rolls that back if
  the entry is later removed from the delta, or if the delta is never delivered.
- Repro: `scripts/s_filtered.py` + `/filtered` page in `elapp/elapp/elapp.py`
  (the `_filtered_get_delta` monkeypatch at the bottom of the module is the whole trigger).
- Evidence: `out/filtered.txt`, `out_prod/filtered.txt`, `out_prev/filtered.txt`,
  `screenshots/dev_filtered_after_show.png`.
- Note for whoever fixes it: `_suppress_delta_recording()` already exists and is exactly the
  right primitive; it is just private and only wired into `reflex/istate/shared.py`.
  A downstream filter has no public way to say "I dropped this, forget you sent it".

### ISSUE-2 — `rx.upload_files` payload cannot resolve `filesById` from a toast/callback scope

- Severity: **high** (the headline use case of #7156's changelog line does not work).
  Regression vs 0.9.11.post1: **no** — baseline fails too, with `queueEvents is not defined`
  for the frontend-fired variant and the same `filesById is not defined` for the
  backend-yielded variant.
- Repro (cases 6, 8, 9 of `scripts/s_callback.py`): put a file in the deferred upload zone
  `u2` (no `on_drop`), then fire any of

  ```python
  on_click=rx.toast("…", action={"label": "Up",
                                 "on_click": CB.handle_upload(rx.upload_files(upload_id="u2"))})
  return rx.toast("…", action={"label": "Up",
                               "on_click": CB.handle_upload(rx.upload_files(upload_id="u2"))})
  return rx.call_script("…", callback=CB.handle_upload(rx.upload_files(upload_id="u2")))
  ```

  Expected: the file uploads and `handle_upload` runs. Observed: nothing uploads; the
  frontend-fired ones raise an uncaught `ReferenceError: filesById is not defined`, the
  backend-yielded ones log `_call_script ReferenceError: filesById is not defined`.
- Evidence: `out/callback.txt` and `out/callback.errors.txt` (`[c1] PAGEERROR filesById is
  not defined`, twice), `out_prod/callback.txt`, `out_prev/callback.txt`.
  Compiled proof, `.web/app_components/elapp/elapp.jsx`:

  ```js
  // inside Button_button_…_0bf88b62 — filesById is NOT declared here
  onClick: () => {addEvents([ReflexEvent("…cb.handle_upload",
      {files: filesById?.["u2"], upload_param_name:"files", upload_id:"u2", extra_headers:{}},
      {}, "uploadFiles")])}
  // …and 120 lines further down, in the component that renders rx.upload:
  const [filesById, setFilesById] = useContext(UploadFilesContext);
  ```

  So the `event_actions`/`handler` slot fix from #7156 is correct and in place; the hook
  that the `rx.upload_files` var depends on is simply not hoisted into the scope that
  contains the toast's `action.onClick`.

### ISSUE-3 — a cancelled foreground superseding handler loses its pre-cancellation state writes under redis

- Severity: **medium**. Regression: **unknown — baseline not checked** (I only ran the
  baseline in dev/memory; a redis prod baseline needs another prod build).
- Repro: `/supersede`, click `fgA` then `fgB` ~0.4 s later
  (`@rx.event(supersedes=True)` non-background, which appends `FA:start`, `yield`s, then
  sleeps 2 s and appends `FA:CANCELLED` on `CancelledError`).
  - dev / in-memory state manager: log is `["FA:start","FA:CANCELLED","FB:start","FB:done"]`.
  - prod / `REFLEX_REDIS_URL`: log is `["FB:start","FB:done"]` — `FA:start` never reaches
    the client and never reaches redis, even though the `yield` before the sleep should have
    flushed it. Reproduced on two consecutive prod runs.
  - The background variant (`rootA`/`rootB`) keeps `A:start, A:CANCELLED` under redis, and a
    foreground handler that runs to completion (`g-mixed`) keeps its writes, so the loss is
    specific to foreground + cancellation + redis.
- Evidence: `out/supersede.txt` (dev) vs `out_prod/supersede.txt` (prod/redis), line
  `[f-foreground]`.

## Benign-but-worth-knowing observations

1. **Every uncached var is re-sent once right after hydrate.** `State.hydrate` emits
   `self.dict()`, which does not go through `_record_delta_value`, so the very next event
   (`on_load_internal`, which fires immediately) re-sends all of them: a 3 318 B hydrate
   frame followed by a 447 B frame containing only the uncached vars. Harmless, but it is
   free bytes left on the table for the first event of every page load. After a *reload*
   (same token, memo already warm) the redundant frame does not appear.
2. **`_UNKEYABLE_VALUE` looks unreachable.** `_delta_value_key` treats a `json_dumps`
   exception as "always send", but reflex's `json_dumps` never raises for unknown types —
   it returns `null` (`complex`, a bare `object()`, an arbitrary class instance all
   serialize to `null`). So two *different* unserializable values key identically and the
   second is dropped from the delta. Functionally harmless (the client would receive `null`
   either way), but the branch is dead and the comment overstates the protection.
   Confirmed live: `Unkeyable.u_obj` (`complex(n, 1)`) is never re-sent across three bumps.
3. **Dict key order defeats the dedupe.** `{"a":1,"b":2}` and `{"b":2,"a":1}` have the same
   contents but different digests, so such a var is re-sent on every event. Intentional
   given the design, just not obvious from the changelog wording ("the value is only
   included in the delta when it actually changed").
4. **An `on_load`-started self-chaining loop is not stopped by client disconnect.** After
   navigating away or reloading mid-loop, the loop keeps running server-side to completion
   and logs one `Warning: Attempting to send delta to disconnected client` per tick — 44 of
   them in `logs/dev_warnings.txt` for this app. Those deltas are *recorded as sent* by
   #6946's memo; that is safe today only because the reconnect path re-hydrates with
   `self.dict()`. Same family of hazard as ISSUE-1.
5. Console noise seen and ignored: the `Disconnect websocket on page navigation` log line
   on client-side navigation; the React Router HydrateFallback banner; vite connect lines.
6. `@rx.memo` without `rx.Var[...]` annotations logs the 0.9.3 deprecation warning — the
   app intentionally keeps the un-annotated form to check the deprecated path still
   compiles and dispatches; it does.

## Cleanup state

All servers (`3180`, `3181`, `3190`), all `react-router dev` children and the redis on
`8195` were killed and verified gone with `$SB/bin/ports.py` and `ps`. `.web/`,
`node_modules/` and `reflex.lock/` are excluded from this directory.
