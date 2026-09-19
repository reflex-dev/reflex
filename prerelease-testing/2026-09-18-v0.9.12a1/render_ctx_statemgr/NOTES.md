# Cluster `render_ctx_statemgr` — reflex 0.9.12a1 pre-release QA

Per-state context providers (#6181), stable ThemeProvider/EventLoopProvider values (#6180),
`StateManagerDisk.set_state`/debounce (#7159), `_get_was_touched` persistence (#7132).

Everything below was run against packages installed **from PyPI only**. Nothing was installed
from `/home/user/reflex`, and no repro was run with the checkout as its working directory.

## Environments

```
# 0.9.12a1 (shared prebuilt venv, $SB/envs/shared)
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

# baseline (prev stable, $SB/envs/prev)
reflex==0.9.11.post1
reflex-base==0.9.11.post1
reflex-components-core==0.9.9
reflex-components-radix==0.9.9
... (the matching stable component set)
```

Rebuilding these from scratch (never from the checkout directory):

```bash
SB=/tmp/.../scratchpad          # any neutral dir
cd $SB
uv venv $SB/envs/shared --python 3.11
uv pip install --python $SB/envs/shared/bin/python --prerelease=allow \
    'reflex==0.9.12a1' 'reflex-components-core==0.9.10a1' 'reflex-components-radix==0.9.10a1' \
    'reflex-components-code==0.9.6a1' 'reflex-components-dataeditor==0.9.3a1' \
    'reflex-components-gridjs==0.9.2a1' 'reflex-components-markdown==0.9.4a1' \
    'reflex-components-plotly==0.9.7a1' 'reflex-components-recharts==0.9.4a1' \
    'reflex-components-sonner==0.9.4a1'
uv venv $SB/envs/prev --python 3.11
uv pip install --python $SB/envs/prev/bin/python 'reflex==0.9.11.post1'
# playwright driver venv: playwright 1.63 + httpx; chromium at /opt/pw-browsers/chromium
uv pip freeze --python $SB/envs/shared/bin/python | grep -i reflex   # record this
```

Ports used: frontend 3220 (new), 3221 (baseline), 3222 (diskapp), 3223 (prod); backend
8220/8221/8222. Every command passed `--frontend-port`/`--backend-port` explicitly.
All client-side HTTP was run with `NO_PROXY=localhost,127.0.0.1` (never exported into the
server's environment).

## Apps

| dir | what it is |
| --- | --- |
| `renderapp/` | render-count probe app: 10 substates (A–H + Store1/Store2 + Page2State + LateState), `@rx.memo` sections, two `rx.ComponentState` instances, `rx.foreach` over 300 rows, `rx.color_mode_cond` + `rx.color_mode.button`, an event-loop consumer button, `rx.LocalStorage`/`rx.Cookie`/`rx.SessionStorage`, `rx._x.client_state`, a background task, an event chain, `on_load` touching two sibling substates, a second page and a dynamic route. Setting `RENDERAPP_EXTRA_STATE=1` adds `BackendOnlyState`, a substate the compiled frontend does not know about. |
| `renderapp_prev/` | byte-identical copy run on 0.9.11.post1 for baselines. |
| `diskapp/` | `StateManagerDisk` probe app plus a custom Starlette `api_transformer` exposing `/api/poke`, `/api/peek`, `/api/set_fresh`, `/api/disk_read`, `/api/double_set`, `/api/dump` so disk contents, the manager's in-memory cache and its write queue can be inspected from outside the websocket. |

`RenderProbe` is a `rx.el.Span` subclass whose `add_hooks` bumps
`window.__renders["<name>"]` on every render, so render counts are read straight out of the page.
Dev mode roughly doubles counts (React StrictMode); prod does not. The tables below therefore
compare **same mode, different version** only. Do not compare a dev number against a prod number:
prod is exactly half of dev for every event-driven scenario, but *not* for the initial load
(see the prod section), so "dev = 2 x prod" is not a safe general rule here.

## Rerun commands

```bash
SB=...; A=$SB/apps/render_ctx_statemgr
export REFLEX_TELEMETRY_ENABLED=false

# 1. render counts, 0.9.12a1 (dev)
cd $A/renderapp && $SB/envs/shared/bin/reflex run --frontend-port 3220 --backend-port 8220 \
   > $A/logs/dev_new.log 2>&1 &
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python $A/scripts/drive_render.py \
   http://localhost:3220 $A/out new_dev

# 2. same on the 0.9.11.post1 baseline
cd $A/renderapp_prev && $SB/envs/prev/bin/reflex run --frontend-port 3221 --backend-port 8221 \
   > $A/logs/dev_prev.log 2>&1 &
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python $A/scripts/drive_render.py \
   http://localhost:3221 $A/out prev_dev

# 3. StateManagerDisk (#7159)
cd $A/diskapp && REFLEX_STATE_MANAGER_MODE=disk \
   $SB/envs/shared/bin/reflex run --frontend-port 3222 --backend-port 8222 > $A/logs/disk_new2.log 2>&1 &
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python $A/scripts/drive_disk2.py \
   http://localhost:3222 http://localhost:8222 $A/out disk_new3 $A/diskapp/diskapp/diskapp.py
#   (the 5th argument is the file the script touches to force a hot reload for step D7)

# 4. shutdown flush, with a debounce long enough that only a shutdown flush can explain a write
cd $A/diskapp && REFLEX_STATE_MANAGER_MODE=disk REFLEX_STATE_MANAGER_DISK_DEBOUNCE_SECONDS=30 \
   $SB/envs/shared/bin/reflex run --frontend-port 3222 --backend-port 8222 > $A/logs/disk_debounce30.log 2>&1 &
NO_PROXY=localhost,127.0.0.1 curl -s --noproxy '*' \
   "http://localhost:8222/api/set_fresh?token=probe-0002&value=FLUSH-ON-SHUTDOWN-2"
ls -t --time-style=+%T -l $A/diskapp/.states/*.pkl | head -1      # note the newest mtime
kill -TERM <pid of the reflex python process, NOT the shell wrapper>
ls -t --time-style=+%T -l $A/diskapp/.states/*.pkl | head -1      # written at the SIGTERM second

# 5. FINDING-036 re-test (delta for a substate the compiled frontend has no dispatcher for)
cd $A/renderapp && $SB/envs/shared/bin/reflex run --frontend-port 3220 --backend-port 8220 &   # compile WITHOUT the extra state
#   ... wait for it to serve, then kill it ...
touch $A/renderapp/.web/nocompile          # makes the next run reuse the stale bundle
cd $A/renderapp && RENDERAPP_EXTRA_STATE=1 \
   $SB/envs/shared/bin/reflex run --frontend-port 3220 --backend-port 8220 > $A/logs/mismatch_new.log 2>&1 &
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python $A/scripts/drive_mismatch.py \
   http://localhost:3220 $A/out mismatch_new
#   baseline: same recipe against $A/renderapp_prev on 3221/8221 with $SB/envs/prev/bin/reflex

# 6. reserved-name check for #7132 / #7136 (no server needed)
cd $A && $SB/envs/shared/bin/python $A/scripts/was_touched_check.py
```

## What was verified

### #6181 per-substate context providers — claim holds, modestly

The compiled `.web/utils/context.jsx` changes shape exactly as the PR describes. On
0.9.11.post1 `StateProvider` called `useReducer` once per substate **in its own body** and
built one static `dispatchers` object; on 0.9.12a1 each substate gets a `SubstateProvider`
component that owns its reducer and registers its dispatcher into a `useRef({})` registry from
a `useLayoutEffect`, with a `delete dispatchers[substateName]` cleanup on unmount.
`EventLoopProvider`'s value is now wrapped in `useMemo`. See `evidence/context_jsx_diff.txt`.

Measured render counts (`out/new_dev_result.json` vs `out/prev_dev_result.json`, dev mode,
StrictMode-doubled):

| scenario | probe | 0.9.12a1 | 0.9.11.post1 |
| --- | --- | ---: | ---: |
| page load + `on_load` touching SubA **and** SubB | A / B / dual | **2 / 2 / 2** | 4 / 4 / 4 |
| same load | C…H, colormode, evloop, componentstate | 2 each | 2 each |
| 5 × `SubA.bump` | A | 10 | 10 |
| 5 × `SubA.bump` | B…H | 0 | 0 |
| 5 × `SubC.bump` | C / everything else | 10 / 0 | 10 / 0 |
| chain `SubH → SubC → SubA` | A / C / H / dual | 2 / 2 / 2 / 2 | 2 / 2 / 2 / 2 |
| 5 s background storm on SubB + 10 clicks on SubA | A / B / dual | 20 / 100 / 120 | 20 / 100 / 120 |
| storm: everything not A or B | 0 | 0 |
| 4 × color-mode toggle | colormode / A…H / evloop | 8 / 0 / 0 | 8 / 0 / 0 |
| client-side nav to /page2 and back | foreach_row (300 rows) | 600 | 600 |
| rebuild 300 `rx.foreach` rows | foreach_row / everything else | 600 / 0 | 600 / 0 |

So the **only** measurable win in this app is the initial `on_load`: a delta carrying two
sibling substates renders each affected provider once on 0.9.12a1 where 0.9.11.post1 rendered
it twice. Everything else — per-substate isolation during events, `@rx.memo`, `ComponentState`,
`rx.foreach`, colour-mode toggling, navigation — was already isolated on 0.9.11.post1 and is
unchanged. `longtasks_during_storm` was `[]` (no long tasks) on both versions, and the 300-row
rebuild took 0.046 s (new) vs 0.049 s (prev). Page load was 0.65 s vs 2.02 s, but that is one
sample against a warm vs cold vite and is not a defensible number.

Websocket traffic is identical: 129 received / 54 sent frames on both versions for the same
scripted run; the initial load carries 4 received event frames on both, 2 of which name both
`sub_a` and `sub_b`.

**No regression, no new console error, no failed request, no page error on either version.**

### #6180 stable ThemeProvider / EventLoopProvider values — not observable here

`EventLoopProvider`'s value is now memoised, and the `ThemeProvider` system-preference listener
is attached once. But the probes that would show the win — a memoised section containing an
`on_click` button (event-loop consumer) and a section reading the colour mode — already recorded
**0** extra renders on 0.9.11.post1 when the colour mode was toggled and when the router
navigated. So the claim is not contradicted, but this app cannot demonstrate it either.
Recorded as an anomaly rather than a pass. A component that consumes `EventLoopContext`
*without* sitting behind an `@rx.memo` boundary would be needed to measure it.

### #7159 StateManagerDisk — both halves of the fix verified

With `REFLEX_STATE_MANAGER_MODE=disk` (`out/disk_new3_result.json`):

* **D1** five websocket-driven `bump`s land on disk after the 2 s debounce (`counter: 5`).
* **D2 — debounce flushes the latest value.** `/api/double_set` calls `set_state` twice inside
  one debounce window with **two different** root-state instances (`first-queued`/101 then
  `second-queued`/202). The queue stays at length 1 and the flushed pickle carries
  `second-queued`/202. This is the half of #7159 that only shows with distinct instances — in
  the ordinary websocket path `modify_state` yields the cached instance and hands the *same*
  object back to `set_state`, so `queued_item.state = state` is a no-op there.
* **D3 — a state never obtained from `get_state` is persisted.** `/api/set_fresh` builds
  `app._state(_reflex_internal_init=True)`, sets a var, clears `dirty_vars` and `_was_touched`,
  and calls `set_state`. The value reaches disk (`fresh-persisted`/999).
  `_mark_replacement_state_touched` does its job.
* **D4** `app.modify_state(BaseStateToken(ident=client_token, cls=app._state))` from a custom
  Starlette route both **pushes the delta live to the open browser tab** and persists to disk;
  the value survives a page reload and `api_writes` increments.
* **D6** 20 sets inside ~0.8 s leave `rapid-20`/20 on disk.
* **D7** editing the app module (hot reload, worker restart) does **not** lose state: the same
  client token still shows `counter=20`, `value=rapid-20` after the reload, served from disk.
* **Shutdown flush.** With `REFLEX_STATE_MANAGER_DISK_DEBOUNCE_SECONDS=30`, a write queued at
  04:52:0x was flushed to `.states/*.pkl` at **04:52:08 — the exact second `SIGTERM` was sent**,
  30 s before the debounce would have fired. `_flush_write_queue()` on cancellation works.

### #7132 `_get_was_touched` — the changelog line is unreachable

One-line confirmation of the orchestrator's FINDING-002 (`scripts/was_touched_check.py`):

```
0.9.12a1      plain_var:    StateValueError: State name `_get_was_touched` is reserved by BaseState; use a different name instead.
              computed_var: StateValueError: ... reserved by BaseState ...
0.9.11.post1  plain_var:    ALLOWED (class created)
              computed_var: ALLOWED (class created)
```

The underlying fix is real and present (`reflex/istate/manager/token.py` now calls
`BaseState._get_was_touched(state)` through the class instead of `state._get_was_touched()`),
but #7136 made the name reserved at class creation, so no app on 0.9.12a1 can reach the code
path the changelog line describes. Note this is also an undocumented breaking change: an app
that declared `_get_was_touched` on a state now fails to import.

### Prod mode (`reflex run --env prod --frontend-port 3223 --backend-port 3223`)

The whole `drive_render.py` script was replayed against a production build
(`out/new_prod_result.json`). Everything functional matches dev: colour-mode toggling, the
background storm (A=17, B=51), the background task pushing to a page-2-only substate (11 on
arrival, 12 after a click), the dynamic route (`pid` = `abc`), all three client-storage kinds
surviving a reload, `client_state` correctly empty after a reload, the second tab getting its
own token, and direct-loading `/page2`. `page_errors`, `failed_requests` and `bad_responses`
are all empty; 127 received / 54 sent websocket frames against 129/54 in dev.

Render counts are exactly **half** of dev for every event-driven scenario (5 x `bump` = 5
renders, colour-mode x4 = 4, storm = 50 on B, 300-row rebuild = 300 rows) — i.e. one render per
delta per affected provider, with no unrelated provider touched. Nav to /page2 and back remounts
the page (300 `foreach_row` renders), same as dev.

The initial load differs from dev in a way worth recording: in prod, `A` and `B` render **2x**
while `C`-`H`, `PAGE`, `colormode`, `evloop` and `componentstate` render **1x** — the hydrate
delta and the `on_load` delta land as two separate commits because prod is fast enough that the
first render completes before the second delta arrives. In dev all probes read 2, i.e. the two
deltas coalesce into a single extra render. Either way only the two substates the `on_load`
actually touched re-render; the isolation claim holds in both modes.

No prod-mode baseline was captured on 0.9.11.post1 (out of timebox), so the prod numbers are
absolute, not a comparison.

One prod-only console error appears and is **my app's fault, not the framework's**:
`Failed to load resource: ... 404`. It is `GET /favicon.ico`, which 404s because `renderapp/`
was hand-written rather than produced by `reflex init` and has no `assets/` directory.
`/manifest.json`, `/sw.js` and `/robots.txt` also 404; `/sitemap.xml` returns 200.

## Issues found

### I-1 (HIGH, **pre-existing, not a regression**) — a delta for a substate the compiled frontend does not know about latches the frontend permanently dead

Re-test of the previous campaign's FINDING-036, same repro shape, on this train.
`#6181` rewrote dispatcher registration but `\.web/utils/state.js` is byte-identical between the
two versions around the fatal branch (`backend_state_mismatch = true`, and `processEvent()`
returns early forever after).

Repro (step 5 above). `out/mismatch_new_result.json` (0.9.12a1) and
`out/mismatch_prev_result.json` (0.9.11.post1) are the same in every field that matters:

```
A_after_load            "0"     (on_load never applied; expected "1")
A_after_clicks          "0"
sent_frames_from_clicks 0       <-- ZERO websocket frames leave the browser
events_reach_backend    false
after_reload_sent_frames 0      <-- reloading does not recover
console_errors          Cannot process state update: no dispatch function for substate(s)
                        "reflex___state____state.renderapp___renderapp____backend_only_state". ...
```

The console message tells the user to refresh or clear the cache; neither helps. Every control
in the app is inert from the first hydrate onward while the backend stays healthy. Two
independent fixes are still plausible: do not treat a delta for an unknown substate as fatal
(drop the substate and warn), and/or do not send substates the page did not ask for.

`#6181` also makes the latch *newly reachable by timing*: dispatchers are now registered from a
`useLayoutEffect` with a `delete` on unmount, instead of living in a static object for the tree's
lifetime. Nothing in my runs hit that window (layout effects for the commit all run before
`EventLoopProvider`, mounted below them, opens the socket, exactly as the PR comment says), but
it is worth knowing that the fatal branch now depends on effect ordering.

### I-2 (MEDIUM, **pre-existing, not a regression**) — `app.modify_state("<client token>")` raises `ValueError: Invalid path: ('',)`

The deprecated-but-supported legacy string form of `app.modify_state` fails for the obvious
argument — the client token as handed to you by `rx.State.router.session.client_token`:

```python
async with app.modify_state(token) as root_state:   # token = "c4d16108-b4fa-..."
```

```
File ".../reflex/app.py", line 1842, in modify_state
    token = BaseStateToken.from_legacy_token(token, root_state=self._state)
File ".../reflex/istate/manager/token.py", line 247, in from_legacy_token
    state_cls = root_state.get_class_substate(tuple(state_path.split(".")))
File ".../reflex/state.py", line 1477, in get_class_substate
    raise ValueError(msg)
ValueError: Invalid path: ('',)
```

`_split_substate_key` partitions on `"_"`, so a bare token yields an empty state path. The
legacy format the code actually wants is `f"{client_token}_{State.get_full_name()}"`. The
deprecation warning that fires just before the crash says "Use `rx.BaseStateToken(token,
state_cls)` instead", which *is* the fix — but the user sees a raw `ValueError` about a path
they never wrote, from an API route that returns a bare HTTP 500.

`from_legacy_token` is byte-identical in 0.9.11.post1 (`diff` of the function bodies in both
site-packages trees), so this is not a regression. Evidence: `logs/disk_new.log` (full
traceback), `out/disk_new3_result.json` step `D5_legacy_bare_token_modify_state` (HTTP 500), and
step `D4_modify_state_api_route` showing the `BaseStateToken` form working.

### I-3 (LOW, **pre-existing, not a regression**) — `reflex run` deletes the entire `.states` directory at startup, in prod too

`reflex/reflex.py::_run` calls `reset_disk_state_manager()` unconditionally
("Delete the states folder if it exists"), which unlinks every `.pkl` in `.states/`. It runs
before the app starts, for `--env dev`, `--env preview` and `--env prod` alike, whatever
`REFLEX_STATE_MANAGER_MODE` is set to.

Consequence: state written by `StateManagerDisk` never survives a `reflex run` restart, only a
hot reload. I verified it directly — after a clean SIGTERM flush wrote six pickles, the next
`reflex run` left `.states/` empty and both probe tokens read back `null`. That makes the disk
state manager's persistence effectively process-scoped, which is reasonable in dev but
surprising for `--env prod`. Identical line in 0.9.11.post1 (`reflex.py:570` there,
`reflex.py:596` here), so pre-existing. Worth a documentation note if it is intended.

## Benign-but-surprising observations (anomalies, not defects)

* **Two token classes with different `cache_key` shapes.** The websocket path uses
  `BaseStateToken`, whose `cache_key` is the bare ident and whose `str()` is the legacy
  `"<ident>_<full.state.name>"`. `StateToken(ident=..., cls=...)` — the class a reader of
  `reflex.istate.manager.token` is likely to reach for first — produces `cache_key`
  `"<ident>/<module.Class>"` and a different `token_path()` md5. Using the wrong one does not
  error: `set_state` happily writes a *second*, parallel state tree under a different cache key
  and a different pickle file, and `sm.states` then holds two entries for the same client. My
  first pass at the disk tests silently measured that parallel universe. `out/disk_new2_result.json`
  is that run, kept as evidence. Nothing here is wrong, but the two classes are easy to confuse
  and the failure mode is invisible.
* **`reflex run` does not exit on `SIGTERM`.** The `reflex run` python process was still alive
  20–30 s after `kill -TERM`, still holding the backend port, but no longer answering HTTP
  (`curl` hung). The state-manager shutdown flush *did* run. `SIGKILL`ing the parent then
  orphans the `react-router dev` node process, which keeps the frontend port bound and makes the
  next `reflex run` exit immediately — this happened twice and had to be cleaned up by pid.
  (Signal handling belongs to the `dev_server_cli` cluster; noted here only because it shaped
  these runs.)
* **vite killed with `exit code -9`.** Twice, the frontend died at startup with
  `Starting frontend failed with exit code -9` / `script "dev" was terminated by signal SIGKILL`,
  and reflex tore the whole app down. Free memory was 13 GB at the time I checked, so this looks
  like a transient spike on this shared 4-CPU box rather than a framework problem. Recorded
  because "frontend failed with exit code -9" is not a self-explanatory message.
* **`REFLEX_API_URL` did not override the compiled api_url** for a `reflex run --frontend-only`
  run: `.web/env.json` still carried `localhost:8000`. Not investigated further; I pinned the
  ports through the `nocompile` route instead. Also note `reflex run --frontend-only` rejects
  `--backend-port` ("Cannot specify --backend-port when not running backend"), so there is no
  CLI-only way to point a frontend-only dev server at a non-default backend port.
* Client-storage vars behave the same on both versions and land in the right providers:
  `rx.LocalStorage` and `rx.Cookie` (two different substates) survive a reload and are visible
  in a second tab; `rx.SessionStorage` survives a reload and is correctly absent in the new tab;
  `rx._x.client_state` is correctly empty after a reload. A second tab gets a **different**
  client token, so its `SubA.count` is 1, not the first tab's value — expected, not a bug.
* `page.emulate_media(color_scheme="dark")` does not flip the rendered colour mode once the user
  has explicitly toggled it (the explicit choice is stored). Same on both versions.
* Dev-server log noise seen on both versions and not reported: the `SitemapPlugin`
  "enabled by default but not explicitly added" warning (3–4× per start), the implicit Radix
  Themes deprecation warning, and `rx._x` experimental warning.

## Not covered

* **A prod-mode 0.9.11.post1 baseline.** Prod was exercised on 0.9.12a1 only, so the prod
  numbers above stand alone and no prod-mode regression claim is made.
* **Redis.** `#7132`'s redis half was not exercised — the reserved-name error (see above) makes
  the scenario unreachable regardless of backend.
* **A late-mounted first consumer across a real code-split boundary.** `rx.cond`-gated and
  page-2-only substates were covered (both fine: a background task started on page 1 pushed 10
  increments to a page-2-only substate, and navigating to page 2 afterwards showed 11), but not
  a `React.lazy`/`rx.dynamic` boundary that mounts a provider after the socket is already open.

## File map

```
renderapp/            render-count probe app (0.9.12a1)
renderapp_prev/       identical source, run on 0.9.11.post1
diskapp/              StateManagerDisk probe app + inspection API routes
scripts/drive_render.py     drives renderapp, writes <label>_result.json + <label>_wsframes.txt
scripts/drive_disk2.py      drives diskapp end to end (D0–D8)
scripts/drive_disk.py       first (wrong-token-class) pass, kept for the anomaly above
scripts/drive_mismatch.py   FINDING-036 re-test
scripts/was_touched_check.py  #7132/#7136 reserved-name check, no server needed
scripts/initial_renders.py    repeats a cold page load N times and prints render counts
out/new_dev_result.json     render counts + everything observed, 0.9.12a1
out/prev_dev_result.json    same on 0.9.11.post1
out/disk_new3_result.json   StateManagerDisk results (the authoritative run)
out/disk_new2_result.json   the wrong-token-class run (evidence for the token anomaly)
out/new_prod_result.json    render counts + everything observed, 0.9.12a1 prod build
out/mismatch_new_result.json / out/mismatch_prev_result.json   FINDING-036 re-test, both versions
out/*.png                   screenshots
logs/                       server logs (dev_new, dev_prev, disk_*, mismatch_*)
evidence/context_jsx_diff.txt   the #6181 diff in compiled output
```
