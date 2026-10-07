# Cluster `ent_grid` — enterprise demos on reflex 0.10.0a2 + OFFLINE reflex-enterprise 0.9.7a4 wheel

Resumed cluster (the first agent was cut off at 07:45 UTC with no NOTES.md; its AG Grid dev/prod runs on a2 are
kept under `out/ag_dev_a2`, `out/ag_prod_a2*` and were not redone). This agent (11:27 UTC on) added the
baselines, root-caused the prod-only AG Grid failure, and drove the remaining demos.

## Environment / venvs (all PyPI + the offline wheel by file path; never the checkouts)

```
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad
WHEEL=$SB/downloads/enterprise_wheel/reflex_enterprise-0.9.7a4-py3-none-any.whl
cd $SB
# under test (built like alpha2-ent, plus the ag_grid demo requirements)
uv --no-config venv --python 3.12 $SB/envs/ent_grid-a2
uv --no-config pip install --python $SB/envs/ent_grid-a2/bin/python --prerelease=allow 'reflex[db]==0.10.0a2' 'pydantic<2.14' "$WHEEL[mcp]" faker==36.2.2 pandas==2.2.3 aiosqlite greenlet
# baselines: same command with 'reflex[db]==0.9.12' (envs/ent_grid-s912) and 'reflex[db]==0.10.0a1' (envs/ent_grid-a1)
```
Resolved: a2 → reflex/reflex-base 0.10.0a2, components-core 0.10.0a2, sqlalchemy 2.1.3, sqlmodel 0.0.48, greenlet 3.5.6
(greenlet MUST be added by hand — N-001), pydantic 2.13.5. s912 → reflex 0.9.12, components-core 0.9.10.post1,
sqlalchemy 2.1.3, sqlmodel 0.0.48. a1 → reflex 0.10.0a1, sqlalchemy 2.0.54, sqlmodel 0.0.44. All three: reflex-enterprise 0.9.7a4 (offline wheel).
No login gate appeared in any run with `CI=true` (the offline wheel never asked for `reflex login`).

Helper scripts (in `scripts/`): `start_server.sh <venv> <app_dir> <log> <poll_url> -- <reflex run args>` (setsid, records the
pgid in `pids/current.pid`, polls up to 6 min; exports CI=true REFLEX_TELEMETRY_ENABLED=false), `stop_server.sh` (kills the
process group, verifies ports 3300-3319/8300-8319 are free), `sync_dest.sh` (copies artifacts to DEST). Drivers run as
`NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python scripts/<driver> ...`; every driver starts with
`assert_driver_and_server(<venv>)` which checks the server process cmdline and where reflex/reflex_enterprise import from.

## 1. AG Grid demo (`apps/ag_grid`, copied from /home/user/reflex-enterprise/demos/ag_grid + `ag_grid/qa_extras.py` QA pages)

The demo rxconfig only sets `async_db_url`; the ModelWrapper pages need a sync URL too, so every run passes
`REFLEX_DB_URL=sqlite:///reflex.db` (without it, "Generate Friends" raises `ValueError: No database url configured` on
every version — `logs/ag_grid-prod-s912-nodburl.log`; demo config issue, not a framework bug).
`reflex db migrate` first (logs/ag_grid-db-migrate-*.log).

Commands (prod; dev is the same with `--frontend-port 3300 --backend-port 8300` and no `--env prod`):
```
REFLEX_DB_URL=sqlite:///reflex.db scripts/start_server.sh ent_grid-a2 $W/ag_grid logs/ag_grid-prod-a2.log http://localhost:3301/ -- --env prod --frontend-port 3301 --backend-port 3301 --loglevel debug
python scripts/smoke_routes.py      http://localhost:3301 out/ag_prod_a2 ent_grid-a2          # 20 routes
python scripts/drive_ag_features.py http://localhost:3301 out/ag_prod_a2_runN ent_grid-a2     # 43-47 checks
python scripts/drive_ag_model.py    http://localhost:3301 out/ag_prod_a2 ent_grid-a2 $W/ag_grid/reflex.db
python scripts/probe_state_coldefs.py http://localhost:3301 out/ag_prod_a2 ent_grid-a2 prod-a2
scripts/stop_server.sh
```
Baselines: same app copied to `baseline/ag_grid_s912` (port 3302, venv ent_grid-s912) and `baseline/ag_grid_a1` (port 3303, venv ent_grid-a1).

| run | smoke routes | features | model wrapper (SSRM/infinite/simple/auth) | state-var column defs probe |
|---|---|---|---|---|
| a2 dev  (first agent) | 20/20, 0 console errors | 46/47 (only `clipboard gold row0->row4`) | 24/29 | n/a (features memo check passes) |
| a2 prod (first agent, 3 runs) | 20/20 | 39/43 ×3, identical | 24/29 | **3/7: State-var grids empty on full load** |
| 0.9.12 prod (this agent) | — | 46/47 (only `clipboard gold row0->row4`) | 24/29, the same 5 not-ok | 7/7 |
| a1 prod (this agent) | — | — | — | **3/7, same as a2** |
| a2 prod + `REFLEX_FRONTEND_LAZY_BUNDLED_LIBRARIES=true` | — | — | — | 6/6 (fixed) but `/formatters` crashes (React #130) |

### 1a. FAIL (regression since 0.10.0a1, prod only): AG Grid with `column_defs` from a State var renders NO columns on a full page load
- `/master-detail` left grid (`column_defs=MasterDetailState.column_defs`), `/qa-grid-memo` (`@rx.memo` grid with
  `State.fields.foreach(...)` column defs, two `rx.ComponentState` grids): header row empty and rows without cells
  (screenshot `out/ag_prod_a2/probe_state_coldefs-prod-a2-master-detail-full-load.jpg`; 0.9.12 prod
  `out/ag_prod_s912/probe_state_coldefs-prod-s912-master-detail-full-load.jpg` shows the columns). Reproduced 3/3 on a2 prod
  (`out/ag_prod_a2_run{1,2,3}`), on a1 prod (`out/ag_prod_a1`), never on 0.9.12 prod, never in dev.
- The grid recovers only when that substate changes (toggle a field) or after client-side navigation to the page.
  A reload does NOT fix it (unless the state differs from its compiled default).
- The four prod-only not-ok checks of the 10-06 partial run (`master_detail: scenario completed`,
  `memo grid: column defs from State.fields.foreach`, `qa_memo: scenario completed`) are all this bug (the driver waits
  for a group-expand cell / a name cell that never renders). They are real, not driver timing.
- Root cause (from the compiled output): enterprise compiles a Var `column_defs` to `formatColumnDefs(state.column_defs)`;
  `formatColumnDefs` returns `[]` when `typeof __reflex === 'undefined'`. Reflex sets `window.__reflex` in a `useEffect` of
  `ReflexProviders` (`.web/app/root.jsx`, identical in 0.9.12 and 0.10), which runs AFTER the page's first render. On 0.9.12
  every state consumer re-rendered once after the boot hydrate, so the grid recomputed with `__reflex` defined; on 0.10 a
  component whose substate is unchanged by the hydrate never re-renders (prod: SSR-hydrated first render), so it stays empty.
- Core-only repro (no enterprise): `apps/core_rerender` + `scripts/probe_core_rerender.py`. A text rendering
  `FunctionStringVar("((v) => (typeof __reflex === 'undefined' ? 'NO_REFLEX' : 'HAS_REFLEX') + ...)").call(Untouched.cols)`:
  - a2 prod: `NO_REFLEX:["a","b"]` after full load AND after reload; becomes HAS_REFLEX only after another var of the same substate changes or client nav.
  - 0.9.12 prod: `HAS_REFLEX` after full load. a2 dev: `HAS_REFLEX`.
  - A substate changed by on_load (`Touched`) and the root state re-render fine on a2.
  ```
  scripts/start_server.sh alpha2 $W/core_rerender logs/core_rerender-prod-a2.log http://localhost:3305/ -- --env prod --frontend-port 3305 --backend-port 3305
  python scripts/probe_core_rerender.py http://localhost:3305 out/core_rerender_prod_a2 alpha2 prod-a2
  # baseline: copy to baseline/core_rerender_s912, venv `stable`, port 3306
  ```
- Workaround: `frontend_lazy_bundled_libraries=True` (new 0.10 config; `window.__reflex` is then assigned at module scope)
  fixes the State-var grids (`out/ag_prod_a2_lazyflag`), but then `/formatters` crashes ("An error occurred while rendering
  this page", Minified React error #130, `out/ag_prod_a2_lazyflag/formatters-lazyflag-0.jpg`) because the demo's
  formatter module is now loaded lazily — consistent with the flag's documented caveat, so not a clean workaround.

### 1b. pre-existing (same on 0.9.12 + same wheel) — enterprise demo / ModelWrapper issues, not regressions
- `ssrm: filtered rows all match and count matches db`, `infinite: text filter matches db`: after a text filter the grid shows
  the matching row(s) followed by ~20 permanent "Loading rows..." placeholder rows (the datasource answers with the stale
  cached unfiltered `rowCount`; `out/ag_prod_a2/ag_model-ent_grid-a2-ssrm-filtered.jpg`). Same on 0.9.12 prod
  (`out/ag_prod_s912/ag_model-ent_grid-s912.json`) and in the 10-06 mixed-graph run.
- `ssrm: rows render on reload right after generate`: the demo only calls setRowCount (row_count_cached interval 10 s); rows
  appear after >10 s. Same on 0.9.12.
- `infinite: add dialog inserts row` / `closes after submit`: the insert raises `sqlalchemy.exc.StatementError: (TypeError)
  SQLite DateTime type only accepts Python datetime and date objects` — the ModelWrapper add dialog passes the `met` form
  string (`'2020-01-02T03:04:05'`) straight into the model (also `PydanticSerializationUnexpectedValue(Expected datetime ... input_type=str)`
  warnings on cell edits). Same traceback on 0.9.12 (`logs/ag_grid-prod-s912.log`) and on a1 (sqlalchemy 2.0).
- `clipboard: Ctrl+C/Ctrl+V copies gold row0 -> row4 and fires change event` fails on a2 dev, a2 prod AND 0.9.12 prod; the
  QA page's ClipboardModule check (copy/paste + on_cell_value_changed) passes everywhere → driver assumption about that demo page.
- `/model`, `/model-auth`, `/model-ssrm`, `/qa-model-workaround` load and serve data on a2 dev+prod (no `from_request` AttributeError: F-001 enterprise consequence fixed).
- Console: `AG Grid: warning #129 headerCheckbox is only available if using clientSide or serverSide rowModelType, you are using infinite`
  on `/model-auth` (both versions; demo config).

## 2. dnd demo (`apps/dnd`, react-dnd HTML5 backend) — PASS on a2 dev + prod

```
scripts/start_server.sh ent_grid-a2 $W/dnd logs/dnd-dev-a2.log http://localhost:3310/ -- --frontend-port 3310 --backend-port 8310 --loglevel debug
python scripts/drive_dnd.py http://localhost:3310 out/dnd_dev_a2 ent_grid-a2 dev-a2
# prod: --env prod --frontend-port 3311 --backend-port 3311 ; out/dnd_prod_a2
```
27/27 checks in dev and in prod, 0 console errors/warnings, 0 failed requests, no server tracebacks. Real pointer drags
(mouse down → stepped moves → jiggle inside the target → up): /basic and /foreach (`@rx.memo` targets inside `rx.foreach`):
hovered target turns green via `DropTarget.collected_params.is_over`, drop moves the card (State.card_pos), `on_drop`
toast, drop outside a target is a no-op, position survives reload, a new browser context starts at 0, demo dropdown
navigation. /kanban: first load does NOT write the `kanban_data_json` LocalStorage default (F-002 class OK on a2), columns
and items via forms, item drag across columns (`can_drop` rxe.static callback), same-column reorder, column drag reorder,
`on_end` toast, board restored from LocalStorage after reload (on_load + backend `_columns`/`_items` dataclasses with a
`__drag_type__` dunder class attribute), second tab sees the same board.
- Driver note: without the in-target jiggle the `is_over` colour sample is taken before react-dnd processed a dragover
  (first attempt showed 2 not-ok checks); with it 27/27 — driver timing, not a bug.
- Benign: console `log` lines "Disconnect websocket on page navigation" / "... on pagehide" (reflex info logs, every page).
- Benign/pre-existing: compile progress shows `100% 18/17` (the counter overshoots its total by one on every app and on 0.9.12 too: ag_grid 50/49, core_rerender 14/13).
- No baseline needed (nothing failed).

## 3. flow demo (`apps/flow`, React Flow) — a2 dev 22/22; prod 20/22 with the SAME 2 not-ok on 0.9.12 prod

```
scripts/start_server.sh ent_grid-a2 $W/flow logs/flow-dev-a2.log http://localhost:3312/ -- --frontend-port 3312 --backend-port 8312 --loglevel debug
python scripts/drive_flow.py http://localhost:3312 out/flow_dev_a2 ent_grid-a2 dev-a2
# prod a2: port 3313 (out/flow_prod_a2); baseline 0.9.12 prod: copy to baseline/flow_s912, venv ent_grid-s912, port 3314 (out/flow_prod_s912)
python scripts/probe_flow_reload.py http://localhost:3313 out/flow_prod_a2_reloadN ent_grid-a2 prod-a2-runN
```
Covered (all pass on a2 dev and prod): 11 nodes / 6 edges, minimap/controls/background, pointer drag of a node
(controlled `on_nodes_change` → `set_nodes(apply_node_changes(...))`), toolbar emoji → State, button-edge × (rx.run_script
set_edges/get_edges), dimension input → `set_dimensions` resizes the node, select + Backspace deletes a node, zoom-in control,
add-node-on-edge-drop (`on_connect_end` + `screen_to_flow_position`, two drops), a new session starts with the initial node
(no cross-session leak of the `default_factory=lambda: initial_nodes` list), connection-limit (second connection refused),
custom node colour input → label, background `bg_color`, minimap `node_color` ArgsFunctionOperation + `rx.match` on a State
var, `on_connect` adds an animated edge, drag-handle (label does not drag, handle does), intersections highlight via throttled
`on_node_drag` + `get_intersecting_nodes`.

### 3a. pre-existing (0.9.12 prod identical), prod only: controlled React Flow edits are reverted by a page reload
- Move a node on /overview, reload the tab (prod): the node is back at its initial position, and the BACKEND state is
  overwritten too (a 2nd reload/client nav also shows the default). a2 prod 5/5 runs (once it survived reload 1 and
  reverted on reload 2), 0.9.12 prod 3/3 (`out/flow_prod_s912_reload{1,2,3}`); a2 dev 3/3 survive (`out/flow_dev_a2_reload*`).
- Mechanism (websocket capture in `probe_flow_reload-*.json`): the prerendered page mounts React Flow with the compiled
  default `nodes` (no `measured`), React Flow emits dimension changes, and `set_nodes(apply_node_changes(OverviewState.nodes,
  changes))` is built from the stale client copy and sent right after `hydrate_and_load` (0.9.12: after `hydrate` +
  `on_load_internal`), so the backend is reset to the defaults (`"id":"1-2",...,"position":{"x":0,"y":100},"measured":{...}`).
  In dev the route renders after hydration with already-measured nodes, so no change event is sent.
- Not a regression (same on 0.9.12); worth a docs/enterprise note: events whose payload is computed from State vars during
  mount in prod use the compiled defaults, not the session state.
- Driver notes: the index shows 7 links in prod (the rxe "Built with Reflex" badge link appears in prod only, both versions);
  a pointer click on the first × lands on an overlapping edge-interaction path (both versions, demo layout), so the driver
  dispatches the click on the button; Backspace-delete waits for `.selected` (controlled selection round trip).

## 4. mantine demo (`apps/mantine`) — PASS 22/22 on a2 dev, a2 prod and 0.9.12 prod; one pre-existing reflex page error

The demo only registers /dates, /pill, /tags-input (accordion/action-icon/alert/anchor/angle-slider/aspect-ratio pages are
commented out upstream: those components do not exist in `rxe.mantine` 0.9.7a4). This cluster added
`mantine/qa_mantine.py` (/qa-mantine): Autocomplete, MultiSelect, RingProgress, JsonInput, NumberFormatter and Collapse bound
to State.
```
scripts/start_server.sh ent_grid-a2 $W/mantine logs/mantine-dev-a2.log http://localhost:3315/ -- --frontend-port 3315 --backend-port 8315 --loglevel debug
python scripts/drive_mantine.py http://localhost:3315 out/mantine_dev_a2 ent_grid-a2 dev-a2
python scripts/probe_mantine_pageerror.py http://localhost:3315 ent_grid-a2
# prod a2: port 3316 (out/mantine_prod_a2); 0.9.12 prod: copy to baseline/mantine_s912, venv ent_grid-s912, port 3317 (out/mantine_prod_s912)
```
Checks: 12 date cards; DatePicker / MonthPicker / YearPicker / DatePickerInput popover / preset buttons built from
`rx.Var("dayjs()...")` / TimeInput (`type=time`) all fire their `on_change` toasts with the right ISO values; pills + `on_remove`;
TagsInput controlled by State (add with Enter, remove, duplicate rejected, survives reload); QA page: Autocomplete
`on_option_submit` → State, MultiSelect `on_change` → list State, RingProgress label/sections from State, JsonInput `on_change`
+ `format_on_blur` + `validation_error`, Collapse `in_` from State, NumberFormatter of a State expression.

### 4a. pre-existing (identical on 0.9.12): reflex's global `window.onerror` throws on error events without an Error object
- Clicking an option in the Mantine MultiSelect triggers the browser's benign "ResizeObserver loop completed with undelivered
  notifications" ErrorEvent (its `error` argument is `null`). Reflex's handler in `.web/utils/state.js`
  (`window.onerror = function (msg, url, lineNo, columnNo, error) { ... info: error.name + ": " + error.message ... }`)
  dereferences `error` and throws `TypeError: Cannot read properties of null (reading 'name')` (page error
  `at window.onerror (utils/state.js:1195)` in dev; same in prod and on 0.9.12 prod — `out/mantine_*/mantine-*.json` page_errors,
  `scripts/probe_mantine_pageerror.py` output). Effect: an uncaught page error on every such event and nothing reported to
  `handle_frontend_exception`; the same applies to cross-origin "Script error." events. In dev vite also logs
  `[vite] (client) [Unhandled error] Error: ResizeObserver loop ...` in the server log.
- Enterprise gap (not reflex): `rxe.mantine.autocomplete` has no `on_change` trigger (only `on_option_submit`, `on_position_change`),
  so a controlled `value=` Autocomplete cannot be built; passing `on_change` raises
  `ValueError: The Autocomplete does not take in an on_change event trigger` at compile.
- Driver notes: the MultiSelect `id` lands on the inner input covered by the wrapper (click via focus + ArrowDown, then click the visible option).
