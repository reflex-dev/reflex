# ent_map_dnd_flow — reflex-enterprise 0.9.5 map / dnd / flow demos on reflex 0.9.11a1

Cluster: `ent_map_dnd_flow`. Tested 2026-09-11 with **PyPI packages only**:
`reflex==0.9.11a1` + `reflex-enterprise==0.9.5` (shared venv `$SB/envs/ent`) against the
baseline `reflex==0.9.10.post2` + `reflex-enterprise==0.9.5` (`$SB/envs/entbase`,
created for this cluster), Python 3.11.15.
Demo sources copied **unmodified** from the read-only clone
`/home/user/reflex-enterprise/demos/{map,dnd,flow}` (repo HEAD 592d5cc, 2026-09-03);
nothing was ever installed from that checkout.

## TL;DR

| app | mode | reflex 0.9.11a1 + rxe 0.9.5 | baseline 0.9.10.post2 + rxe 0.9.5 |
|---|---|---|---|
| map demo (leaflet) | dev | **13/13** + **7/7** extra | not needed (nothing failed) |
| dnd demo (react-dnd) | dev | **18/18** | **18/18** (run, identical) |
| flow demo (xyflow), **unpatched** | dev | **11/11** + **9/9** extra | not needed |
| `entlab` custom app (map+dnd+flow × core reflex) | dev | **20/20** | not needed |
| all three demos | **prod** | **BLOCKED** by reflex-enterprise's paid-tier gate | **BLOCKED** identically |

All four apps run clean: **0 page errors, 0 non-benign browser console messages, 0 4xx/5xx,
0 server-log tracebacks**. The only failed requests anywhere are `*.tile.openstreetmap.org`
(blocked by this sandbox's egress proxy — environmental, present on both versions).

### Status of the 0.9.9a1 enterprise breakage (asked explicitly)

| previous finding (2026-08-27) | status on reflex 0.9.11a1 + rxe 0.9.5 | how verified here |
|---|---|---|
| **FINDING-001** `dynamic.bundled_libraries` removed | **FIXED, both sides.** reflex ships a deprecation shim (`reflex.components.dynamic.bundled_libraries` returns the active `RegistrationContext`'s list and emits a `DeprecationWarning`), and rxe 0.9.5 no longer needs it: `reflex_enterprise/vars.py:28 get_bundled_libraries()` reads `RegistrationContext.ensure_context().bundled_libraries` with the old attribute only as fallback. | `logs/shim_check.txt`; `logs/repro_dnd_can_drop_0911a1.log` |
| **FINDING-021** ag-grid python-callable renderer/formatter crash | **FIXED** (mechanism). The masking crash came from the same `bundled_libraries` read; that read is gone. The ag-grid *end-to-end* re-verification belongs to the `ent_aggrid` cluster of this campaign, which reports it compiling and running. | mechanism verified here, e2e cross-referenced |
| **FINDING-022** non-static `can_drop` + `bundle_library()` imports | **FIXED, and now verified end-to-end in the browser** (previously only "constructs without raising"). `repro_finding001_dnd_can_drop.py` exits 0, and `entlab/` drives a real drag against a `can_drop` lambda whose compiled JS is `((item, monitor) => { const format = __reflex['d3-format']?.format; return (format(",")(item?.["price"]).indexOf(",") !== -1) })` — the target lights green for `price=130000` and salmon for `price=42`, and the drop is accepted/rejected accordingly. | `shots/entlab_0911a1_dev/`, driver checks `dnd_bundled_can_drop_*` |
| **FINDING-023** `reflex.page.DECORATED_PAGES` removed | **FIXED.** The flow demo runs **completely unmodified** (byte-identical to `/home/user/reflex-enterprise/demos/flow`); the import now emits a `DeprecationWarning` naming `RegistrationContext.ensure_context().decorated_pages` instead of an `ImportError`. | `flow/flow/flow.py` line 2 unchanged; `logs/flow_0911a1_dev.log:130`; 11/11 + 9/9 driver |
| **FINDING-024** AttributeError masked as `_cached_get_all_var_data` | **NOT re-verified here** — this campaign's `FINDINGS.md` FINDING-013 already records it as still present and pre-existing. My probe (`probe_finding024_mask.py`) failed to reach the masking path and is kept only as a negative control. | cross-reference |
| **FINDING-025** ag_grid demo's stale `$/utils/components` bundle path | **NOT FIXED**, per this campaign's `ent_aggrid/NOTES.md` ISSUE 1. Not re-tested here (different demo), but I independently hit the *related* root cause from the dnd side — see ISSUE A below. | cross-reference + ISSUE A |
| **FINDING-026** `/_reflex/cookies/sync` 404 in the OIDC demo | **not in this cluster** (OIDC demo). Not tested. | — |
| **FINDING-029** rxe error paths emit `console.error` DeprecationWarning | **NOT FIXED** with rxe 0.9.5. Both gates still do it: `reflex_enterprise/app.py:120` (login gate) and `reflex_enterprise/utils.py:119` (prod/export gate). Identical on 0.9.10.post2 ⇒ downstream, not a regression of this train. | `logs/map_0911a1_login_gate.log`, `logs/map_0911a1_prod_gate.log`, `logs/map_0910post2_prod_gate.log` |

**No regression of the 0.9.11a1 train was found in this cluster.** Four issues are recorded
below; all four reproduce identically on 0.9.10.post2 (three of them are reflex-side
pre-existing defects, one is downstream in reflex-enterprise).

## Setup / how to rerun (exact commands)

```bash
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
D=$SB/apps/ent_map_dnd_flow          # this directory

# demo sources (unmodified copies)
cp -r /home/user/reflex-enterprise/demos/{map,dnd,flow} $D/

# 0.9.11a1 env: the shared read-only venv already has everything the demos need
#   (their requirements.txt list only reflex + reflex-enterprise)
$SB/envs/ent/bin/python -c "import importlib.metadata as m; print(m.version('reflex'), m.version('reflex-enterprise'))"
#   -> 0.9.11a1 0.9.5

# baseline env (cwd must NOT be /home/user/reflex, or uv's exclude-newer hides the alphas)
cd $SB && uv venv $SB/envs/entbase --python 3.11
uv pip install --python $SB/envs/entbase/bin/python 'reflex==0.9.10.post2' 'reflex-enterprise==0.9.5'
```

**`CI=1` is mandatory** — `rxe.App` calls `_check_login()` and `exit()`s with
"``reflex-enterprise`` is free to use but you must be logged in" for an anonymous tier
unless `CI` or `REFLEX_BACKEND_ONLY` is set (`reflex_enterprise/app.py:104`).

Servers (one at a time; ports from this cluster's reserved ranges 5140-5159 / 9540-9559):

```bash
cd $D/map    && CI=1 REFLEX_TELEMETRY_ENABLED=false $SB/envs/ent/bin/reflex run \
                 --frontend-port 5140 --backend-port 9540 --loglevel debug > $D/logs/map_0911a1_dev.log 2>&1 &
cd $D/dnd    && ... --frontend-port 5143 --backend-port 9543 ...   # logs/dnd_0911a1_dev.log
cd $D/flow   && ... --frontend-port 5145 --backend-port 9545 ...   # logs/flow_0911a1_dev.log
cd $D/entlab && ... --frontend-port 5146 --backend-port 9546 ...   # logs/entlab_0911a1_dev.log
# baseline: $SB/envs/entbase/bin/reflex, ports 5148-5150 / 9548-9550, on copies under baseline/
```

Poll `http://localhost:<FP>/` until 200 (first run does a bun install, 1-2 min here), then drive:

```bash
cd $D && NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $SB/envs/driver/bin/python drivers/drive_map.py        http://localhost:5140 $D/shots/map_0911a1_dev        map_0911a1_dev
  $SB/envs/driver/bin/python drivers/drive_map_extra.py  http://localhost:5140 $D/shots/map_0911a1_dev_extra  map_extra
  $SB/envs/driver/bin/python drivers/drive_dnd.py        http://localhost:5143 $D/shots/dnd_0911a1_dev        dnd_0911a1_dev
  $SB/envs/driver/bin/python drivers/drive_flow.py       http://localhost:5145 $D/shots/flow_0911a1_dev
  $SB/envs/driver/bin/python drivers/drive_flow_extra.py http://localhost:5145 $D/shots/flow_0911a1_dev_extra
  $SB/envs/driver/bin/python drivers/drive_entlab.py     http://localhost:5146 $D/shots/entlab_0911a1_dev     entlab
```

Every driver prints one `RESULT PASS/FAIL <check>` line per check plus console /
network-failure / page-error summaries, writes screenshots + `capture.json`
(or `results*.json`) into its shots dir, and exits non-zero on any FAIL.
`drivers/drive_map.py`, `drive_dnd.py`, `drive_flow.py` and `drivers/common.py` are
carried over unchanged from the 2026-08-27 `ent_map_dnd` / `ent_misc` clusters, so the
comparison with that campaign is apples-to-apples.

## What was tested

### map demo (leaflet) — 13/13 + 7/7 extra, dev

`drive_map.py` (unchanged from the previous campaign): index cards; `/map-controls`
non-default control placement (zoom topright, scale bottomleft, attribution topleft);
`/fly-to-location` two markers, hover tooltip, popup with a working `rx.toast` button,
mouse-wheel zoom → debounced `on_zoom` state round-trip (13 → 17), click-on-map
`on_click=lambda e: my_api.set_view(...)`, drag-pan, `MapAPI.fly_to`, `locate()` with mocked
geolocation (51.6, -0.2) → `on_locationfound`; `/vector-layers` circle/circle-marker/polygon/
polyline/rectangle (5 SVG paths + 1 marker) and `get_bounds(callback=rx.console_log)`.

`drive_map_extra.py` (**new this campaign**): the second, `draggable=True` marker really
moves with the mouse and stays where it is dropped; popup open **and** close via the close
button; "Locate and setView"; "Fly to Found Location" after a location exists; client-side
(SPA) navigation to all three sub-routes and back with the leaflet map re-mounting each
time; hard reload of the deep route `/vector-layers`.

### dnd demo (react-dnd) — 18/18 dev on 0.9.11a1, **18/18 dev on the 0.9.10.post2 baseline**

Index; `/basic` and `/foreach` real mouse-down/move/up drags with the `is_over` highlight
sampled *while holding* (`rgb(0,0,255)` → `rgb(0,128,0)`), `on_drop` toast + state move, drag
back; `/kanban` create 2 columns + 2 items through the forms, drag an item between columns
(`@rxe.static` `can_drop` preview), `on_end` toast, column reorder by dragging a heading, and
localStorage persistence across reload. Byte-for-byte the same result on both versions.

### flow demo (xyflow) — 11/11 + 9/9 extra, dev, **demo unmodified**

`drive_flow.py`: index (6 pages, built through the now-shimmed `DECORATED_PAGES`);
`/overview` 11 nodes / 6 edges / minimap / controls, node drag round-trip, node-toolbar emoji
(🚀→🔥); `/nodes/custom-node`; `/nodes/drag-handle` (handle drags, body inert);
`/nodes/connection-limit` connect + limit enforcement; `/nodes/add-node-on-edge-drop`;
`/nodes/intersections` highlight.

`drive_flow_extra.py` (**new**), aimed at the deletion path the brief calls out:
single-node select + delete (11 → 10) and it *sticks* through the
`on_nodes_change` → `apply_node_changes` → state round-trip; edge select + delete (5 → 4);
shift box-select 7 nodes + delete (10 → 3); `/nodes/connection-limit` connect-then-delete
the created edge; SPA navigation across all 6 routes with back-navigation; and node position
persisting across a **hard reload** and across SPA navigate-away-and-back.

`drivers/probe_flow_persist2.py` is the isolated persistence probe:
`before (0,100) → dragged (86.3,157.5) → after hard reload (86.3,157.5) → after SPA back
(86.3,157.5)`, and `multiselect 11 → 3 nodes, still 3 after reload`.

### entlab — a purpose-built app combining all three libraries with core reflex

`entlab/entlab/entlab.py` (20/20). Three pages:

* `/dnd` — the FINDING-022 surface driven for real. A **non-`@rxe.static`** `can_drop`
  lambda whose return expression carries an import from a `bundle_library()`-registered
  package (`d3-format`), next to an `@rxe.static` control with the opposite predicate.
  Also `@rx.memo` draggables, `rx.cond` slots, `rx._x.client_state` hover counter
  (`hovers: 17` after the drags) and `@rx.event(background=True)` fired from the drop
  event chain (`bg_ticks: 1`). Result: `pricey` (130000) is accepted by the bundled-library
  target (lightgreen while over, `log: pricey->0`), `cheap` (42) is rejected (salmon, log
  unchanged) and accepted by the static target (`log: pricey->0,cheap->1`).
* `/map` — leaflet markers built with `rx.foreach` over a state list (3 → 4 after
  `add_point`), an `rx.cond` circle overlay that toggles off, a popup button firing a state
  event (`clicked: alpha`), an `rx.ComponentState` counter (`clicks: 2`) and `MapAPI.fly_to`.
* `/flow` — xyflow nodes coming from an `@rx.var` **computed var**: add node from the
  backend (`counts: 3/0`), handle-to-handle connect through `on_connect` + `add_edge`
  (`counts: 3/1`), and Backspace delete (`counts: 2/1`).

### prod mode — BLOCKED on both versions (licence gate, not circumvented)

`reflex run --env prod --frontend-port 5141 --backend-port 5141` exits at
`reflex_enterprise/utils.py:82 check_paid_tier_for_command()`:

```
`reflex run --env prod` requires a paid Reflex subscription (one of pro, team, enterprise).
You are currently logged out. Run `reflex login` to authenticate.
```

`CI=1` does **not** bypass this (only the dev-mode `_check_login` honours `CI`), and
`reflex export` is gated by the same function. Verified byte-identical on
0.9.10.post2 + rxe 0.9.5 (`logs/map_0910post2_prod_gate.log`), so this is not a change in
this train. The gate has exactly one exemption in rxe's own code —
`if is_in_app_harness(): return`, i.e. `reflex.constants.APP_HARNESS_FLAG` set — **which I
deliberately did not use**: setting that flag purely to get past a paid-subscription check
would be circumventing the vendor's licence gate, not testing it. Consequence to record for
the release: **prod-mode coverage of reflex-enterprise apps is structurally unavailable to
unlicensed QA**; if the team wants it, run this cluster's drivers from an account on a paid
tier (or from reflex-enterprise's own CI, which is exempt).

## Issues (all four reproduce identically on 0.9.10.post2 — none is a regression of this train)

### ISSUE A (MEDIUM, pre-existing, reflex) — `bundle_library()` called at app-module import time is silently discarded before pages are evaluated

`reflex/compiler/compiler.py::compile_app()` calls `reset_bundled_libraries()`
(line 1212) *after* the app module has already been imported, then re-adds only the
plugin-declared frontend dependencies. Any `bundle_library("x")` the user made at module
scope is therefore gone by the time the compiler evaluates the pages, and the failure
surfaces far away from the cause.

On the dnd surface the user sees, at app start:

```
ValueError: Library d3-format is not bundled. Use `from reflex.components.dynamic import
bundle_library; bundle_library('d3-format') to enable it it.
  ... reflex_enterprise/vars.py:166 _validate_and_extend_return_expr
Happened while evaluating page 'dnd'
```

— i.e. the error tells you to do the exact thing you already did. (Note also the doubled
"it it" typo in that reflex-enterprise message.)

Self-contained repro (**pure reflex, no reflex-enterprise**), in `bundlectx/`:

```bash
cd $D/bundlectx && REFLEX_TELEMETRY_ENABLED=false $SB/envs/ent/bin/reflex export --frontend-only --no-zip
```

```
PROBE import      ctx= 0x7f63d74921a0 bundled= [... , 'd3-format', 'react']
PROBE after_app   ctx= 0x7f63d74921a0 bundled= [... , 'd3-format', 'react']
PROBE page_eval   ctx= 0x7f63d74921a0 bundled= [... , 'react']     <-- d3-format gone
```

Same `RegistrationContext` object (identical `id()`), list mutated in place by
`reset_bundled_libraries()`. Identical output on 0.9.10.post2
(`logs/bundlectx_0910post2.log` vs `logs/bundlectx_0911a1.log`).

Workaround: call `bundle_library()` **inside the page function** (what
`entlab/entlab/entlab.py::dnd_page` does).

Same root cause as this campaign's `ent_aggrid` ISSUE 1 (found from the ag-grid `@rx.memo`
side); recorded here because the dnd/LambdaVar entry point produces a different, more
misleading message and because two independent clusters hitting it argues for fixing it
rather than documenting it. `bundle_library` has no mention anywhere in `docs/`.

Second, app-level repro that produces the traceback above verbatim (`bundlectx_dnd/`,
an rxe app whose only `bundle_library()` call is at module scope):

```bash
cd $D/bundlectx_dnd && CI=1 REFLEX_TELEMETRY_ENABLED=false $SB/envs/ent/bin/reflex run \
    --frontend-port 5151 --backend-port 9551        # exit 1, ValueError above
cd $D/baseline/bundlectx_dnd_base && CI=1 ... $SB/envs/entbase/bin/reflex run \
    --frontend-port 5152 --backend-port 9552        # exit 1, identical
```

- Evidence: `bundlectx/`, `bundlectx_dnd/`, `logs/bundlectx_0911a1.log`,
  `logs/bundlectx_0910post2.log`, `logs/issueA_dnd_traceback_0911a1.log`,
  `logs/issueA_dnd_traceback_0910post2.log`.

### ISSUE B (MEDIUM, pre-existing, reflex) — a hook-bearing component used directly inside `rx.foreach` compiles cleanly and then throws `ReferenceError` in the browser

`rxe.dnd.draggable` emits a `useDrag` hook. Used directly as the `rx.foreach` render
function, the hook is hoisted out of the generated `.map()` closure but keeps referencing
the loop variable, so the generated JSX is:

```js
const [draggableCollectedParams, drag_ref_osizayzf, ...] =
  useDrag({ type: "LabItem", item: { id: iid_rx_state_, ... } }, []);   // iid_rx_state_ undefined here
```

The page compiles with no warning; at runtime React throws
`ReferenceError: iid_rx_state_ is not defined at Foreach (...)` and the **entire page** is
replaced by the error boundary. Wrapping the same body in `@rx.memo` works.

Repro (`foreachhook/`, two routes: `/` raw and `/memo`):

```bash
cd $D/foreachhook && CI=1 REFLEX_TELEMETRY_ENABLED=false $SB/envs/ent/bin/reflex run \
    --frontend-port 5147 --backend-port 9547
cd $D && NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python \
    drivers/probe_foreach_hook.py http://localhost:5147 $D/shots/foreachhook/a1
```

`/` → `draggables: 0`, body "An error occurred while rendering this page… ReferenceError:
iid_rx_state_ is not defined"; `/memo` → `draggables: 2`, clean.
Identical on 0.9.10.post2 (port 5148, `shots/foreachhook/base0910_*.png`).

The check is cheap to add: when a component produced inside a `foreach` render function
contributes hooks whose code references the loop var, raise at compile time with a message
pointing at `@rx.memo` (the pattern the shipped dnd demo already uses).

- Evidence: `foreachhook/`, `drivers/probe_foreach_hook.py`,
  `shots/foreachhook/a1_raw.png`, `shots/foreachhook/base0910_raw.png`,
  `logs/foreachhook_0911a1.log`, `logs/foreachhook_0910post2.log`.

### ISSUE C (LOW, pre-existing, reflex-components-core) — the framework's own error boundary logs three React "Invalid DOM property" errors every time it renders

`reflex_components_core/base/error_boundary.py:85` passes SVG attributes in kebab-case:

```python
"stroke-linecap": "round",
"stroke-linejoin": "round",
"stroke-width": "2",
```

React 19 rejects those on a DOM element, so every crash page adds three
`console.error: Invalid DOM property \`stroke-linecap\`. Did you mean \`strokeLinecap\`?`
lines *above* the real exception — noise in precisely the console a developer is reading to
find the real error, and three false positives for any test harness that fails on
`console.error`. Fix is three renames to `strokeLinecap` / `strokeLinejoin` / `strokeWidth`.

Repro: any page that throws — e.g. ISSUE B's `/` route above; the three messages precede
the `ReferenceError` in `probe_foreach_hook.py`'s output. Identical on 0.9.10.post2
(reflex-components-core 0.9.9 in both). The `hmr_runtime` cluster of this campaign saw the
same three lines next to its ErrorBoundary hit but did not file them.

- Evidence: `shots/foreachhook/a1_raw.png`, driver output in
  `logs/foreachhook_probe_a1.txt` and `logs/foreachhook_probe_base0910.txt`, generated
  `Errorboundary_*.jsx` excerpt in `logs/error_boundary_jsx_excerpt.txt`.

### ISSUE D (LOW, pre-existing, downstream: reflex-enterprise 0.9.5) — previous campaign's FINDING-029 is still open

Both enterprise gates call the deprecated `console.error`, so the user's last message before
the process exits is a framework DeprecationWarning rather than the actual reason:

* login gate — `reflex_enterprise/app.py:120`, reproduce with
  `cd $D/map && env -u CI REFLEX_TELEMETRY_ENABLED=false $SB/envs/ent/bin/reflex run --frontend-port 5149 --backend-port 9549`
  (`logs/map_0911a1_login_gate.log`);
* prod/export gate — `reflex_enterprise/utils.py:119`, reproduce with
  `cd $D/map && CI=1 ... reflex run --env prod --frontend-port 5141 --backend-port 5141`
  (`logs/map_0911a1_prod_gate.log`).

Identical on 0.9.10.post2 (`logs/map_0910post2_prod_gate.log`) ⇒ downstream, not a
regression. Fix belongs in reflex-enterprise (`logger.error` / `console.print`).

## Benign-but-surprising observations (recorded, not filed as issues)

1. **OSM tiles are unreachable in this sandbox.** 77-120 `net::ERR_TUNNEL_CONNECTION_FAILED`
   failures per map driver run against `*.tile.openstreetmap.org`. Environmental (the egress
   proxy blocks the host), present on both versions; every leaflet interaction works anyway
   because panes/SVG do not need the tile bitmaps.
2. **Demo-code deprecation warnings** — identical on both versions, all from demo source, none
   from the released libraries:
   * `Passing strings to disable_plugins` (0.8.28) — all three `rxconfig.py`;
   * `@rx.memo on <name> without explicit annotations` — 9 components in dnd, 9 in flow;
   * `Passing base-component prop(s) key to @rx.memo` — dnd;
   * `ArrayVar.foreach` → use `ArrayVar.map` (0.9.7) — `flow/intersections.py:71,76`;
   * `App(theme=...)` → `RadixThemesPlugin(theme=...)` (0.9.0) — flow demo,
     surfaced from `reflex_components_radix/plugin.py:100`;
   * `Implicit Radix Themes enablement` (0.9.0) — map, dnd.
3. **`reflex.page.DECORATED_PAGES` deprecation fires twice** per `reflex run` (once per
   process that imports the app module — compiler and backend worker). Cosmetic.
4. **xyflow's delete key is Backspace, not Delete.** `deleteKeyCode` defaults to `Backspace`
   upstream, so pressing `Delete` on a selected node is a no-op. Not a reflex/rxe defect —
   noted because a first version of `drive_flow_extra.py` reported a false failure for it
   (`shots/flow_probe_0911a1/probe_persist.json`, `delete_key: selected 1, count unchanged`).
5. **`fit_view=True` makes screen coordinates a bad persistence oracle.** After a remount
   xyflow re-fits the viewport, so a node that really did keep its state position lands at a
   different screen position. `drive_flow_extra.py` therefore compares the node's inline
   `transform: translate(x,y)` (flow coordinates). Same false failure trap as (4).
6. **`rxe.dnd.drop_target` has no `on_dragenter` trigger** — the valid hover trigger is
   `on_hover`. The error message is good (it lists the valid triggers).
7. **Frontend dependency drift, flow demo, 0.9.9a1 → 0.9.11a1** (`pkgjson/flow_deps_099a1_vs_0911a1.txt`):
   react-router / @react-router/* 8.3.0 → 8.3.1, vite 8.2.0 → 8.2.2, postcss 8.5.23 → 8.5.26,
   postcss-import 16.1.1 → 17.0.0, sonner 2.0.7 → 2.0.8, isbot 5.2.1 → 5.2.2. The enterprise
   deps (leaflet 1.9.4, react-leaflet 5.0.0, react-dnd 16.0.1, @xyflow/react) are unchanged.
8. **`reflex run` can leave an orphan vite/react-router process** if the parent exits
   abnormally (observed once while iterating on `entlab`): the frontend kept serving 200 on
   5146 with a dead backend. Not reproducible on demand, so not filed; worth remembering
   when a "working" frontend has no websocket.

## Artifact map

```
map/ dnd/ flow/            unmodified reflex-enterprise demo sources (no .web/.states/venvs)
entlab/                    purpose-built map+dnd+flow × core-reflex app (20/20)
bundlectx/                 ISSUE A minimal repro (pure reflex, no enterprise)
bundlectx_dnd/             ISSUE A app-level repro on the rxe dnd/LambdaVar surface
foreachhook/               ISSUE B minimal repro (/ raw vs /memo)
baseline/                  0.9.10.post2 copies actually used for the baseline runs
drivers/common.py          Playwright harness (console/network capture, localhost proxy bypass,
                           mocked geolocation) — unchanged from the 2026-08-27 cluster
drivers/drive_map.py       13 checks, unchanged from 2026-08-27
drivers/drive_dnd.py       18 checks, unchanged from 2026-08-27
drivers/drive_flow.py      11 checks, unchanged from 2026-08-27 (ent_misc)
drivers/drive_map_extra.py    7 new checks (marker drag, popup close, SPA nav, deep reload)
drivers/drive_flow_extra.py   9 new checks (node/edge/multi delete, SPA nav, persistence)
drivers/drive_entlab.py       20 checks for entlab
drivers/probe_flow_persist.py / probe_flow_persist2.py   isolated persistence probes
drivers/probe_foreach_hook.py                            ISSUE B probe
repro_finding001_dnd_can_drop.py   FINDING-022 construction repro (exit 0 on 0.9.11a1)
probe_finding024_mask.py           negative control only, see table above
logs/                      server logs (trimmed), gate outputs, probe outputs
shots/                     screenshots + capture.json / results*.json per run
pkgjson/                   .web/package.json per app + the cross-train dependency diff
```

## VERIFICATION: bundle_library() called at app-module import time is silently discarded before pages are evaluated, so the documented dynamic-import path fails with an error telling you to do what you already did

Independent adversarial verification (2026-09-11, second agent, own working dir
`$SB/apps/verify2_ent_map_dnd_flow_0/`, own repro apps written from the claim text —
the claimant's `bundlectx/` / `bundlectx_dnd/` sources were read but not executed and
none of their processes were used).

**VERDICT: CONFIRMED — genuine reflex-core defect, reproduced independently on two
surfaces. Severity MEDIUM. NOT a regression of the 0.9.11a1 train (identical on
0.9.10.post2). NOT downstream (root cause is `reflex/compiler/compiler.py`).
Three corrections to the claim, all sharpening rather than refuting it — see below.**

### What I reproduced myself

Both repro apps are under
`verification/bundle_library_reset/` and both start with
`assert "/envs/" in rx.__file__` so the venv under test is named in the log
(no `/home/user/reflex` shadowing; no network, ports or proxy are involved —
every failure below is a compile-time Python exception raised before anything is served).

**(1) PURE REFLEX, no reflex-enterprise — `verification/bundle_library_reset/probe1/`.**
`bundle_library("d3-format")` at module scope plus a var-returning `@rx.memo` whose JS
imports `format` from `d3-format`. `BUNDLE_WHERE=page` repeats the same call inside the
page function.

```bash
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
cd <probe1> && BUNDLE_WHERE=module REFLEX_TELEMETRY_ENABLED=false \
  $SB/envs/smoke/bin/reflex export --frontend-only --no-zip     # reflex 0.9.11a1 -> exit 1
cd <probe1> && BUNDLE_WHERE=page   REFLEX_TELEMETRY_ENABLED=false \
  $SB/envs/smoke/bin/reflex export --frontend-only --no-zip     # -> exit 0
cd <probe1_b0910> && BUNDLE_WHERE=module REFLEX_TELEMETRY_ENABLED=false \
  $SB/envs/base0910/bin/reflex export --frontend-only --no-zip  # reflex 0.9.10.post2 -> exit 1
```

`logs/probe1_module_0911a1.log` (reflex 0.9.11a1, exit 1):

```
PROBE import     ctx=0x7f33c6ffb520 bundled=['$/utils/context', '$/utils/state', '@emotion/react', 'd3-format', 'react']
PROBE after_app  ctx=0x7f33c6ffb520 bundled=['$/utils/context', '$/utils/state', '@emotion/react', 'd3-format', 'react']
PROBE page_eval  ctx=0x7f33c6ffb520 bundled=['$/utils/context', '$/utils/state', '@emotion/react', 'react']
TypeError: Var-returning `@rx.memo` `fmt_label` cannot import `d3-format` because it is
not bundled. Use a component-returning `@rx.memo` instead.
```

`logs/probe1_module_0910post2.log` (reflex 0.9.10.post2): byte-identical probe lines and
the same `TypeError`. `logs/probe1_page_0911a1.log` (workaround): `page_eval` still holds
`d3-format`, exit 0, and the built `.web/app/root.jsx` then really does carry
`import * as d3_format from "d3-format";` / `"d3-format": d3_format,` in the
`window.__reflex` map — i.e. the lost registration is a real loss of the frontend bundle
entry, not merely a validator complaint.

**(2) reflex-enterprise dnd surface — `verification/bundle_library_reset/dndbundle/`.**
Non-`@rxe.static` `can_drop` returning a `Var` with `imports={"d3-format": [...]}`,
`bundle_library("d3-format")` at module scope only.

```bash
cd <dndbundle> && CI=1 BUNDLE_WHERE=module REFLEX_TELEMETRY_ENABLED=false \
  $SB/envs/ent/bin/reflex run --frontend-port 5840 --backend-port 10240      # exit 1
cd <dndbundle> && CI=1 BUNDLE_WHERE=page   REFLEX_TELEMETRY_ENABLED=false \
  $SB/envs/ent/bin/reflex run --frontend-port 5840 --backend-port 10240      # "App running"
cd <dndbundle_b0910> && CI=1 BUNDLE_WHERE=module REFLEX_TELEMETRY_ENABLED=false \
  $SB/envs/entbase/bin/reflex run --frontend-port 5841 --backend-port 10241  # exit 1
```

`logs/dndbundle_module_0911a1.log` (reflex 0.9.11a1 + rxe 0.9.5) reproduces the claimed
traceback verbatim, doubled typo included:

```
ValueError: Library d3-format is not bundled. Use `from reflex.components.dynamic import
bundle_library; bundle_library('d3-format') to enable it it.
Happened while evaluating page 'index'
```

`logs/dndbundle_module_0910post2.log` (reflex 0.9.10.post2 + rxe 0.9.5): identical.
`logs/dndbundle_page_0911a1.log`: with the call moved into the page function the app
compiles and reaches `App running at: http://localhost:5840/`, and `root.jsx` gains the
`d3-format` window entry. Server killed; ports 5840/10240 free.

### Mechanism (read on `origin/r/pre-2026.09.10-34457666442`, matches the installed wheel)

* `reflex/compiler/compiler.py:1212` — `compile_app()` calls `reset_bundled_libraries()`.
* `reflex/compiler/compiler.py:1217-1219` — it then re-adds **only**
  `plugin.get_frontend_dependencies()`.
* `reflex/compiler/compiler.py:1236` — `compile_ctx.compile()` evaluates the pages, i.e.
  after the reset.
* `packages/reflex-base/src/reflex_base/components/dynamic.py:72-75` —
  `reset_bundled_libraries()` does `bundled[:] = _default_bundled_libraries()`, an
  in-place slice assignment on `RegistrationContext.ensure_context().bundled_libraries`,
  which is why the context `id()` is unchanged while the entry vanishes.
* Consumers that then raise: `packages/reflex-base/src/reflex_base/components/memo.py:819-831`
  (pure reflex, var-returning `@rx.memo`) and `reflex_enterprise/vars.py:163-168`
  (`LambdaVar._validate_and_extend_return_expr`). The silent consumer is
  `reflex_base/components/dynamic.py:140-147`, which falls back to a jsdelivr CDN URL for
  any import whose library is no longer in the registry, and
  `reflex/compiler/compiler.py:149-153`, which builds `window.__reflex` from the same list.

The framework's own supported registration point is *inside* the compile:
`reflex_components_radix/plugin.py:70` calls `bundle_library()` from `enter_component`,
which runs during page compilation — after the reset. Module scope is the only place a
plain app can call it, and it is exactly the place that is wiped.

### Corrections to the claim (none of them refute it)

1. **"documented dynamic-import path" overstates it.** `bundle_library` has *zero*
   occurrences anywhere in `docs/` (`grep -rn bundle_library docs/` -> 0 files); the
   claimant says this too, later in their own write-up, but the issue title contradicts
   it. The path is recommended only by reflex-enterprise's runtime error message. Worth
   keeping the observation, not the word "documented".
2. **The changelog attribution is slightly off.** The claim points at #6382 (the move of
   the list onto `RegistrationContext`, reflex-base 0.9.9). The reset predates that:
   `git log -S "reset_bundled_libraries"` shows it first introduced by **#6260**
   ("Add compiler plugin hooks and plugins and move compilation pipeline out of App",
   86382e2f9, 2026-04-30), whose first tag is `reflex-base-v0.9.2a1`. #6382 only relocated
   the storage. So the behaviour dates to **0.9.2**, not to this train and not to 0.9.9.
   Confirmed at the tags: `git grep -n reset_bundled_libraries v0.9.1` returns nothing
   (the symbol did not exist, so a module-scope registration survived to page evaluation),
   while `git show v0.9.2:reflex/compiler/compiler.py | grep -n reset_bundled_libraries`
   gives line 1047. No changelog entry announced the change. (A runtime cross-check on a
   reflex 0.9.1 venv was attempted twice; both PyPI installs died on the sandbox proxy
   (`Failed to fetch .../reflex-0.9.1-py3-none-any.whl.metadata ... operation timed out`),
   so the boundary rests on the tag-level source evidence -- conclusive for a static code
   question -- plus the maintainer's own report below recording 0.9.8 as byte-identical.)
3. **This is already filed and tracked — the claim is genuine but not novel.**
   [reflex-dev/reflex#6975](https://github.com/reflex-dev/reflex/issues/6975)
   ("compile_app() discards user bundle_library() registrations, and the dynamic
   serializer never rewrites subpath imports of bundled libs"), opened 2026-08-28 by
   masenf, label `bug`, **still open**, Linear ENG-11814. It was filed out of the previous
   (0.9.9a1) campaign's `registration_context` cluster and states defect (1) in the same
   terms, assessing it "Severity: low. Not a regression — behavior is byte-identical on
   0.9.8." So: the correct release action is "still open, not fixed in 0.9.11a1", not
   "new finding".

   #6975 also records an asymmetry neither this cluster nor `ent_aggrid` mentions, and the
   release source confirms it by inspection: the backend-only paths of `compile_app()`
   return at `compiler.py:1186` and `:1204`, **before** the reset at `:1212`, so the
   backend worker keeps the user's registration while the frontend compile drops it —
   frontend bundle and backend registry can end up permanently out of sync in a run that
   does *not* hard-fail.

### Judgement

* `confirmed`: **true**. Not an environment quirk (no network/ports/cwd involvement;
  venv asserted in-process), not API misuse (`bundle_library` is public, has no other
  app-level call site, and the maintainer's own issue calls the module-scope call a
  defect), not a demo bug (reproduced in a 30-line pure-reflex app), not flaky
  (deterministic, 6/6 runs).
* `severity`: **medium**, one notch above #6975's "low", because the two surfaces exercised
  here abort the compile outright rather than degrading silently, and because the
  reflex-enterprise message instructs the user to perform the exact call they already made.
  It is **not a 0.9.11 release blocker**: pre-existing since 0.9.2, already tracked, and
  worked around by one line (call `bundle_library()` inside the page function).
* `regression`: **false** — verified by running the baseline myself
  (`logs/probe1_module_0910post2.log`, `logs/dndbundle_module_0910post2.log`).
* `downstream`: **false** — the fix belongs in `reflex/compiler/compiler.py`. The two
  downstream nits are real but separate: rxe's `"to enable it it"` typo and its message
  not saying *where* to call `bundle_library` (`reflex_enterprise/vars.py:166`).

### Evidence paths

```
verification/bundle_library_reset/probe1/          pure-reflex repro (BUNDLE_WHERE=module|page)
verification/bundle_library_reset/dndbundle/       rxe dnd repro (BUNDLE_WHERE=module|page)
verification/bundle_library_reset/logs/probe1_module_0911a1.log     TypeError, 0.9.11a1
verification/bundle_library_reset/logs/probe1_page_0911a1.log       workaround, exit 0
verification/bundle_library_reset/logs/probe1_module_0910post2.log  baseline, identical
verification/bundle_library_reset/logs/dndbundle_module_0911a1.log  ValueError, 0.9.11a1
verification/bundle_library_reset/logs/dndbundle_page_0911a1.log    workaround, App running
verification/bundle_library_reset/logs/dndbundle_module_0910post2.log  baseline, identical
```

## VERIFICATION: A hook-bearing component used directly inside rx.foreach compiles with no warning and then throws ReferenceError in the browser, blanking the whole page

**Verdict: CONFIRMED — genuine reflex-core defect, and BROADER than ISSUE B described.
NOT a regression (identical on 0.9.10.post2). NOT enterprise-specific: reproduces with
`rx.upload` and `rx.form` on plain `reflex==0.9.11a1` with no reflex-enterprise installed.
Severity for this release train: medium (pre-existing, supported `@rx.memo` workaround);
as a standalone framework bug: high.**

Independent verifier, reproduced from the written repro in a fresh working dir
(`$SB/apps/verify2_ent_map_dnd_flow_1/`), reserved ports 5844-5847 / 10244-10247, one dev
server at a time. All servers killed afterwards (`5844..5847` all return 000).

### Refutation attempts (all failed to explain it away)

| Hypothesis | Result |
|---|---|
| Environment quirk (proxy / ports / cwd shadowing / missing NO_PROXY) | No. `NO_PROXY` set client-side only; `reflex.__file__` asserted to live under `$SB/envs/`; three different apps on three different port pairs all fail identically. Sibling routes in the *same* app render clean. |
| API misuse / documented behaviour | No. `docs/library/dynamic-rendering/foreach.md` (229 lines on the release branch) never mentions hooks, `@rx.memo`, or any restriction; `git grep -niE "hook.*foreach\|foreach.*hook"` over `docs/ reflex/ packages/` returns nothing. `Foreach.create` validates the iterable type and rejects `ComponentState`, but has no hook check. |
| Enterprise (`rxe.dnd`) bug, not framework | No. Reproduced on `$SB/envs/smoke` (reflex 0.9.11a1, **no** reflex-enterprise) with core `rx.upload` and core `rx.form`. |
| Pre-existing on 0.9.10.post2 | **Yes** — confirmed by my own baseline run. Claimant's `regression=false` is correct. The mechanism also predates the memoize rewrite: the legacy `StatefulComponent` pass (`86382e2f9~1:packages/reflex-base/.../component.py:2385`) collected a `Foreach` whole in exactly the same way. |
| Flaky | No. Deterministic on every load of every affected route, in both versions. |

### Minimal repro (pure reflex, no enterprise)

`verification/foreach_hook_scope/pureforeach/` — one app, seven routes:

| route | body | 0.9.11a1 | 0.9.10.post2 |
|---|---|---|---|
| `/` | `rx.foreach(rx.Var.create(["a","b"]), chip)` where `chip` is an `rx.el.Div` subclass whose `add_hooks()` interpolates its own prop | **ReferenceError, page blank, 0 chips** | same |
| `/state` | same, iterating `S.items` (a State var) | **ReferenceError, page blank, 0 chips** | same |
| `/upload` | `rx.foreach(S.items, lambda iid: rx.upload(..., id=iid))` — **core reflex component** | **ReferenceError, page blank, 0 uploads** | same |
| `/form` | `rx.foreach(S.items, lambda iid: rx.form(..., on_submit=lambda _d: S.note(iid)))` — **core reflex component** | renders, but **clicking submit throws `ReferenceError: iid_rx_state_ is not defined`; the event never reaches the backend — silent no-op** | same |
| `/memo` | same chip wrapped in `@rx.memo` | 2 chips, clean console | same |
| `/plain` | one chip, no foreach | 1 chip, clean console | same |
| `/click` | `rx.button(on_click=S.note(iid))` in a foreach | 2 buttons, clean — inline arrow stays inside the `.map()` | same |

`rx.upload` and `rx.form(on_submit=...)` inside `rx.foreach` are the important additions:
both are core, both are ordinary user code, neither is mentioned in ISSUE B.
The `/form` variant is the worst mode — nothing crashes, nothing renders wrong, the submit
just silently does nothing except a console error, and the single hoisted
`handleSubmit_<hash>` is shared by every iteration so it could not have been per-item
correct even if the identifier resolved.

### Exact commands

```bash
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
W=$SB/apps/verify2_ent_map_dnd_flow_1
V=/home/user/reflex/prerelease-testing/2026-09-10-v0.9.11a1/ent_map_dnd_flow/verification/foreach_hook_scope

# A. pure reflex 0.9.11a1 (no reflex-enterprise)
mkdir -p $W && tar -C $V -cf - pureforeach | tar -C $W -xf -
cd $W/pureforeach && REFLEX_TELEMETRY_ENABLED=false CI=1 \
    $SB/envs/smoke/bin/reflex run --frontend-port 5844 --backend-port 10244
cd $W && NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python drivers/probe_routes.py \
    http://localhost:5844 $W/shots/pure_0911a1 \
    '/|[data-chip="1"]' '/state|[data-chip="1"]' '/memo|[data-chip="1"]' \
    '/plain|[data-chip="1"]' '/upload|[data-chip="1"]' '/form|[data-chip="1"]' '/click|[data-chip="1"]'
cd $W && NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python drivers/probe_form_submit.py \
    http://localhost:5844 $W/shots/pure_0911a1

# B. same app on reflex 0.9.10.post2 (fresh copy, no shared .web)
cd $W/pureforeach_base && REFLEX_TELEMETRY_ENABLED=false CI=1 \
    $SB/envs/base0910/bin/reflex run --frontend-port 5845 --backend-port 10245
#   ... same two probe commands against http://localhost:5845

# C. claimant's exact enterprise repro (reflex 0.9.11a1 + reflex-enterprise 0.9.5)
cd $W/foreachhook && REFLEX_TELEMETRY_ENABLED=false CI=1 \
    $SB/envs/ent/bin/reflex run --frontend-port 5846 --backend-port 10246
cd $W && NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python drivers/probe_routes.py \
    http://localhost:5846 $W/shots/dnd_0911a1 '/|[draggable="true"]' '/memo|[draggable="true"]'
```

C reproduced the claim verbatim: `/` -> `matches: 0`, body "An error occurred while
rendering this page ... ReferenceError: iid_rx_state_ is not defined at Foreach
(http://localhost:5846/app_components/foreachhook/foreachhook.jsx:44:15)"; `/memo` -> 2
draggables, clean console.

### Mechanism (release branch `origin/r/pre-2026.09.10-34457666442`)

1. `IterTag.render_component()` —
   `packages/reflex-base/src/reflex_base/components/tags/iter_tag.py:76-113` — calls
   `render_fn(self.get_arg_var())`, where `get_arg_var()` (`iter_tag.py:57-70`) is a bare
   `Var(_js_expr="<param>_rx_state_")`, i.e. **the name of the JS `.map()` callback
   parameter**. Any hook the produced component builds by interpolating that Var is a
   string containing `<param>_rx_state_`.
2. `Foreach.create` —
   `packages/reflex-components-core/src/reflex_components_core/core/foreach.py:110-112` —
   deliberately keeps that rendered component in `self.children` ("Keep a ref to a rendered
   component to determine correct imports/hooks/styles").
3. `Component._get_all_hooks()` —
   `packages/reflex-base/src/reflex_base/components/component.py:2041-2063` — flattens
   `child._get_all_hooks()` for every descendant into one dict emitted **at the enclosing
   React function scope**. It has no notion of the closure `Foreach` introduces, so the
   loop-scoped hook escapes the `.map()`.
4. `Foreach._memoization_mode = MemoizationMode(recursive=False)`
   (`.../core/foreach.py:34`) makes it a snapshot boundary, so
   `MemoizeStatefulPlugin.enter_component` (`reflex/compiler/plugins/memoize.py:232-295`)
   wraps the whole Foreach into one memo component and seals its descendants. The hooks
   therefore land at the top of the generated `Foreach_comp_<hash>` function, directly
   above the `Array.prototype.map.call(...)` that declares the variable they reference.

Generated proof (`verification/foreach_hook_scope/logs/pureforeach_memo_module_0911a1.jsx`,
identical shape in `..._0910post2.jsx`):

```js
export const Foreach_comp_c6156ae8..._bade3042 = memo(({children}) => {
    const reflex___state____state__pureforeach___pureforeach___s = useContext(...)
const chip_label = iid_rx_state_;                      // <-- not defined at this scope
    return(
        Array.prototype.map.call(...items ?? [], ((iid_rx_state_, index_...) => ( ... )))
    )
});
```

and for `rx.upload`:

```js
const { getRootProps: xdvxrcsn, ... } = useDropzone(({ ..., ["id"] : iid_rx_state_, ... }));
```

Note the second, independent wrongness: even if the identifier resolved, **one** hoisted
`useDrag`/`useDropzone`/`handleSubmit` is shared by all N iterations, so per-item hooks can
never be correct inside a `rx.foreach` render function. The supported spelling really is
`@rx.memo` (which lifts the body into its own React component and passes the loop value as
a prop — see `MemoChip_bade3042` in the same generated module).

### Assessment vs the original ISSUE B

* Verdict, regression status and downstream status as claimed: **all correct**.
* "generic codegen behaviour of rx.foreach": correct, and not tied to enterprise.
* Scope understated: it is not only third-party/enterprise hook components. Core
  `rx.upload` and core `rx.form(on_submit=...)` are hit, and the `rx.form` mode fails
  **silently** (no crash, no blank page, submit just never fires).
* The suggested fix (compile-time error pointing at `@rx.memo` when a component built
  inside a `foreach` render function contributes a hook whose text contains the loop
  variable) is sound and cheap: the arg name is already known at
  `iter_tag.py:57` / `foreach.py:_render`, and the child's hooks are already collected at
  `foreach.py:111`. A substring check over `component._get_all_hooks()` for
  `arg_var_name` / `index_var_name` at that point would catch every case above with no
  runtime cost. Not a 0.9.11a1 blocker (pre-existing), but worth a real bug.

### Evidence

* App source: `verification/foreach_hook_scope/pureforeach/pureforeach/pureforeach.py`
* Drivers: `verification/foreach_hook_scope/drivers/probe_routes.py`,
  `.../drivers/probe_form_submit.py`
* Probe output: `verification/foreach_hook_scope/logs/pure_probe_0911a1.txt`,
  `.../pure_probe_0910post2.txt`, `.../pure_form_submit_0911a1.txt`,
  `.../pure_form_submit_0910post2.txt`, `.../dnd_probe_0911a1.txt`
* Generated JSX: `verification/foreach_hook_scope/logs/pureforeach_memo_module_0911a1.jsx`,
  `.../pureforeach_memo_module_0910post2.jsx`,
  `.../dnd_memo_module_excerpt_0911a1.txt`
* Screenshots: `verification/foreach_hook_scope/shots/pure_0911a1_*.png`,
  `.../pure_0910post2_*.png`, `.../dnd_0911a1_{root,memo}.png`

### Side observation (not a new finding)

The three `Invalid DOM property stroke-linecap/stroke-linejoin/stroke-width` console errors
that precede every ReferenceError here are ISSUE C, already filed by the claimant; my runs
reproduce them on both 0.9.11a1 and 0.9.10.post2, confirming that one too.
