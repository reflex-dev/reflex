# ent_map_dnd — reflex-enterprise 0.9.4 map + dnd demos on reflex 0.9.9a1

Cluster: `ent_map_dnd`. Tested 2026-08-28 against PyPI packages only:
`reflex==0.9.9a1` + `reflex-enterprise==0.9.4` (venv099a1) vs baseline
`reflex==0.9.8` + `reflex-enterprise==0.9.4` (venv098), Python 3.11.
Demo sources copied unmodified from `/home/user/reflex-enterprise/demos/{map,dnd}`
(that checkout was used as read-only reference only; nothing was installed from it).

## TL;DR

- **Both demos work end-to-end on 0.9.9a1, identically to 0.9.8**: map 13/13
  Playwright checks, dnd 18/18 (dev mode). Prod mode could not be tested on
  EITHER version: reflex-enterprise gates `reflex run --env prod` behind a paid
  subscription (see anomaly 5).
- **FINDING-001 does NOT fire for the shipped map/dnd demos** — but it is real and
  one lambda away: `repro_finding001_dnd_can_drop.py` shows the exact
  `AttributeError: module 'reflex.components.dynamic' has no attribute
  'bundled_libraries'` (reflex_enterprise/vars.py:143) for a `can_drop` lambda that
  uses the documented `bundle_library()` pattern. Works on 0.9.8, crashes on
  0.9.9a1 → regression (in the reflex-base/enterprise contract, not in demo code).
- Precise trigger conditions mapped below (why the demos escape).

## Why the shipped demos do NOT hit FINDING-001

`LiteralLambdaVar.create` (reflex_enterprise/vars.py) calls
`_validate_and_extend_return_expr` — the only reader of
`reflex.components.dynamic.bundled_libraries` — **only when
`not is_static(func)`**, and the crashing line 143 is only reached when the
lambda's compiled return expression carries VarData **without hooks** (a
state-var reference raises the "cannot use hooks" ValueError at line 138 first,
on both 0.9.8 and 0.9.9a1 equally).

- **map demo**: no LambdaVar-typed props anywhere (`grep LambdaVar` in the wheel:
  only `components/dnd/dnd.py` uses it). The `on_click=lambda e: my_api.set_view(...)`
  is a normal reflex event-trigger lambda, not a LambdaVar. → unaffected.
- **dnd demo**: `basic`/`foreach` pass no `can_drop`/`can_drag`; `kanban`'s
  `_can_drop` functions are decorated `@rxe.static` → validation skipped; the
  DropTarget/Draggable `collect` functions in the wheel are `@static` too.
  → unaffected.
- **Who IS affected** (dnd cluster): any user passing a plain (non-`@rxe.static`)
  function to `rxe.dnd.drop_target(can_drop=...)` / `draggable(can_drag=...)`
  (or any LambdaVar prop) whose return expression carries imports via the
  officially supported `bundle_library()` mechanism — the exact feature this
  validator implements. Crashes at component construction (page definition)
  time on 0.9.9a1. ag-grid value formatters are the higher-traffic route
  (other cluster).

Repro: `repro_finding001_dnd_can_drop.py` — run with each venv's python from the
cluster dir. 0.9.8 → exit 0 ("OK: drop_target ... created"); 0.9.9a1 → exit 1
with the full traceback ending at
`reflex_enterprise/vars.py:143  bundled_libraries = set(dynamic.bundled_libraries)`.
Logs: `logs/repro_finding001_099a1.log`, `logs/repro_finding001_098.log`.

## Setup / how to rerun

```
SB=/tmp/claude-0/-home-user-reflex/20b6ffc8-8244-5bac-b158-8501871b3811/scratchpad
D=$SB/apps/ent_map_dnd          # contains map/, dnd/, drivers/, repro script
uv venv $D/venv099a1 --python 3.11
uv pip install --python $D/venv099a1/bin/python --prerelease=allow 'reflex==0.9.9a1' 'reflex-enterprise==0.9.4'
uv venv $D/venv098 --python 3.11
uv pip install --python $D/venv098/bin/python 'reflex==0.9.8' 'reflex-enterprise==0.9.4'
# provenance check (run from $D, NOT from a dir containing a reflex checkout):
cd $D && ./venv099a1/bin/python -c "import reflex_enterprise, reflex; print(reflex_enterprise.__file__, reflex.__file__)"
```

**IMPORTANT — `CI=1` is required.** `rxe.App` exits at startup with
"`reflex-enterprise` is free to use but you must be logged in." unless a Reflex
access token is configured. `AppEnterprise._check_login` skips the gate when the
`CI` env var is set (or `REFLEX_BACKEND_ONLY`). All runs below use `CI=1`.
Side note: on 0.9.9a1 the login-failure path itself emits
`DeprecationWarning: console.error has been deprecated in version 0.9.9 ...
(reflex_enterprise/app.py:120)` before exiting — enterprise 0.9.4 still calls the
now-deprecated `console.error` (see `logs/map_099a1_run1.log`).

Run servers (one at a time; ports from this cluster's reserved ranges):

```
cd $D/map && CI=1 REFLEX_TELEMETRY_ENABLED=false $D/venv099a1/bin/reflex run \
    --frontend-port 3340 --backend-port 8340 --loglevel debug > $D/logs/map_099a1.log 2>&1 &
# dnd: same with $D/dnd, ports 3341/8341
# 0.9.8 baseline: venv098, map 3342/8342, dnd 3343/8343 (rm -rf .web .states reflex.lock first)
# prod: add --env prod with frontend-port == backend-port; exits at the enterprise
#       paid-subscription gate on both versions (see anomaly 5)
```

Poll `http://localhost:<FP>/` until 200 (first run does a bun install, 1-3 min),
then drive (drivers need playwright; `$SB/envs/driver/bin/python`, Chromium at
`/opt/pw-browsers/chromium`):

```
cd $D && NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $SB/envs/driver/bin/python drivers/drive_map.py http://localhost:3340 $D/shots/map_099a1 map_099a1
  $SB/envs/driver/bin/python drivers/drive_dnd.py http://localhost:3341 $D/shots/dnd_099a1 dnd_099a1
```

Drivers print one `RESULT PASS/FAIL <check>` line per check plus console /
network-failure / page-error summaries, write screenshots + `capture.json`
(all console messages, failed requests) into the shots dir, and exit non-zero on
any FAIL.

## What was tested (all Playwright, real Chromium, real mouse)

### map demo (leaflet) — 13/13 PASS on 0.9.9a1, 13/13 on 0.9.8

- index renders demo cards
- `/map-controls`: map renders; zoom control topright, scale bottomleft,
  attribution topleft (all non-default positions honored)
- `/fly-to-location`: 2 markers; tooltip "Baz bum" on hover; popup on click with
  a working button (`rx.toast` fires from inside leaflet popup); mouse-wheel zoom
  updates state var via debounced `on_zoom` (Zoom: 13 -> 17); click-on-map
  `on_click=lambda e: my_api.set_view(...)` works; drag-pan works; "Fly to
  center" MapAPI call works; "Locate" with mocked geolocation (51.6,-0.2) fires
  `on_locationfound` -> state shows `{"lat":51.6,"lng":-0.2}`
- `/vector-layers`: circle, circle-marker, polygon, polyline, rectangle all
  render (5 interactive SVG paths + 1 marker); `get_bounds(callback=rx.console_log)`
  logs LatLngBounds to browser console

### dnd demo (react-dnd) — 18/18 PASS on 0.9.9a1 (dev), 18/18 on 0.9.8 (dev)

- index renders demo cards
- `/basic` and `/foreach`: real mouse-down/move/up HTML5 drag of the card into
  another drop target; `collected_params.is_over` turns the hovered target green
  mid-drag (verified via computed style while holding the drag); `on_drop` fires
  toast + moves card via state; drag back works
- `/kanban`: create 2 columns + 2 items via forms; drag item card between columns
  (drop preview card rendered green via `can_drop`/`item_by_id` LambdaVar logic —
  the `@rxe.static` client-side path — works at runtime on 0.9.9a1);
  `on_end` toast fires; column reorder by dragging a column heading onto the other
  column; localStorage persistence survives reload (`on_load` restores board)

## Anomalies / quirks observed (all present on BOTH versions unless noted)

1. **[0.9.9a1-only, minor]** `DeprecationWarning: console.error has been
   deprecated in version 0.9.9 ... (reflex_enterprise/app.py:120)` on the
   not-logged-in exit path (see above).
2. `@rx.memo` without-annotations DeprecationWarnings (9 components) and
   "Passing base-component prop(s) `key` to `@rx.memo`" warnings for the dnd
   demo — identical on 0.9.8 (20 occurrences each); demo-code hygiene, not a
   0.9.9a1 issue. Same for "Passing strings to disable_plugins" and "Implicit
   Radix Themes enablement" warnings (both versions).
3. OSM tile fetches (`*.tile.openstreetmap.org`) fail with
   `net::ERR_TUNNEL_CONNECTION_FAILED` in this sandbox (proxy blocks the host) —
   77 failed requests per map driver run on BOTH versions. Environmental, not
   reflex. Map interactions all work regardless (leaflet panes/SVG don't need
   tile bitmaps).
4. The `is_over` green highlight on `/foreach` appears with a slightly longer
   delay than `/basic` (first driver run sampled the color too early and saw
   blue; with a 2.5 s poll-while-holding it always goes green on both pages and
   both versions). Not judged a bug.
5. **Prod mode untestable (both versions, licensing — SKIPPED, not a bug).**
   `reflex run --env prod` with rxe.App exits at startup: "`reflex run --env
   prod` requires a paid Reflex subscription (one of pro, team, enterprise)."
   (`reflex_enterprise/utils.py` check_prod_mode_in_tier; `CI=1` does not bypass
   it, only dev-mode `_check_login` honors CI). Confirmed identical on 0.9.8
   (`logs/dnd_098_prod_gate.log`) and 0.9.9a1 (`logs/dnd_099a1_prod.log`). The
   gate was not circumvented. Two side observations from the attempts:
   (a) on 0.9.9a1 a first attempt with distinct ports exits earlier with "In
   prod mode, frontend and backend must run on the same port." — single-port is
   now mandatory in prod; (b) the prod-gate exit path also triggers the
   `console.error` DeprecationWarning, here at `reflex_enterprise/utils.py:119`
   (same pattern as anomaly 1).

## Artifact map

- `map/`, `dnd/` — demo app sources (copies of reflex-enterprise/demos, no edits;
  `.web`/`.states`/venvs excluded)
- `drivers/common.py` — Playwright harness (console/network capture, proxy
  bypass for localhost, mocked geolocation)
- `drivers/drive_map.py`, `drivers/drive_dnd.py` — the end-to-end drivers
- `repro_finding001_dnd_can_drop.py` — minimal FINDING-001 trigger (dnd path)
- `logs/` — full server logs for every run + repro outputs
- `shots/map_099a1`, `shots/map_098`, `shots/dnd_099a1`, `shots/dnd_098` —
  screenshots + `capture.json` (all console messages, failed requests) per run
- `pkgjson/` — `.web/package.json` per demo per version.
  Diff 0.9.8 -> 0.9.9a1 (both demos): react-router 7.18.2 -> 8.3.0
  (react-router-dom dropped), vite 8.0.16 -> 8.2.0, postcss override removed.
  Enterprise deps identical across versions (leaflet 1.9.4, react-leaflet 5.0.0,
  react-dnd 16.0.1, react-dnd-html5-backend 16.0.1).
