# a3_ent_grid: N-025 re-verification on reflex 0.10.0a3 + reflex-enterprise 0.9.7a5, plus the enterprise#273 regression hunt

Agent `a3_ent_grid`, 2026-10-07 19:39–21:00 UTC. Ports 3300-3319 (prod single port / dev frontend) and 8300-8319 (dev backend).
Work dir `$SB/apps/a3_ent_grid` (`SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad`).
Everything comes from PyPI plus the offline enterprise wheels, installed by file path. No checkout was installed or used as cwd.

STATUS: done. Final report: `../board/results/a3_ent_grid.md`. Inbox: `../board/findings-inbox/a3_ent_grid-{1,2}.md`.

## Verdicts
- **N-025: FIXED** when reflex 0.10.0a3 runs with reflex-enterprise 0.9.7a5, in prod and in dev. All 13 entv scenarios pass,
  including the explorer's `aggrid_min` probe (4/4) and the demo's `/master-detail`, `/qa-grid-memo` and `/formatters` State tab
  (`probe_state_coldefs` 7/7; the a2 pass got 3/7).
- **NOT fixed for a user who upgrades reflex but not enterprise.** On a3 with the 0.9.7a4 wheel, prod still shows the a2-pass
  failure: the state grid is 0h/0c, the memo grids are empty and the detail grid has `[]` headers. reflex a3 did not change the
  ordering, so users must upgrade enterprise to 0.9.7a5 too.
- The enterprise fix alone already fixes reflex 0.10.0a2 (`alpha2-ent-a5`). a5 keeps 0.9.12 working (`s912-ent-a5`).
- Core side unchanged on a3. `corev` shows a render-time `window.__reflex` reader of an unchanged substate stays `NO_REFLEX` on
  a3 prod, as on a2. `window.__reflex` is still assigned in the `ReflexProviders` effect. Boot is still one `hydrate_and_load`
  whose deltas carry only the root state plus substates that on_load changed. Any NON-enterprise code that reads
  `window.__reflex` during render remains affected. That is the maintainer's accepted trade-off (reflex#7492 closed).
- **enterprise#273 regression hunt: no regression found.** Covered: literal and Var-valued column defs, lambda renderers,
  formatters and getters, memo components in cells, master/detail, pinned rows, row grouping and `rx.cond` column defs, in prod
  (full load, reload, client nav) and in dev, on a3, a2 and 0.9.12. Results:
  - 0 page errors.
  - No `ReferenceError`.
  - No React #130, #185 or #418 in the default mode.
  - 0 of 583 traced renderer invocations (a3 prod 80, a3 dev 160, a2+a5 240, 0.9.12+a5 103) ran before `window.__reflex` existed. AG Grid invokes renderers about 100 ms after it.
- `REFLEX_FRONTEND_LAZY_BUNDLED_LIBRARIES=true` is **still broken** for lambdas that return Radix components. Every such page
  crashes with React #130: entv `/renderer`, and entr `/lit`, `/var` and `/memo2`. `/detail2` crashes when its row is expanded.
  This is unchanged from a2 (documented caveat). With a5 the flag is no longer needed as a workaround, so this is low severity.
- AG Grid demo smoke on a3-ent: prod and dev match the a2-pass and 0.9.12 numbers.
  - smoke 20/20
  - features 46/47 (the known clipboard driver assumption)
  - model 24/29 (the same 5 pre-existing ModelWrapper failures)
  - F-001's enterprise half still holds: `/model`, `/model-auth`, `/model-ssrm` and `/qa-model-workaround` serve data, and SSRM
    sort, filter, edit and selection work.
- dnd, flow, mantine and map demos on a3-ent match the a2-pass results. Exceptions are timing flakes in dev under machine load
  (details in §5).

## Venvs (versions printed by `bin/vers.py` at every server start, checked by every driver)
| venv | reflex / reflex-base | reflex-enterprise | role |
|---|---|---|---|
| `a3-ent` (shared) | 0.10.0a3 / 0.10.0a3 (components-core 0.10.0a2, sqlalchemy 2.1.4, greenlet 3.5.6, pydantic 2.13.5) | 0.9.7a5 offline wheel | under test |
| `a3-ent-a4` (shared) | 0.10.0a3 / 0.10.0a3 | 0.9.7a4 offline wheel | user upgrades reflex only |
| `a3` (shared) | 0.10.0a3 / 0.10.0a3 | — | core-only corev |
| `alpha2-ent` (shared) | 0.10.0a2 / 0.10.0a2 | 0.9.7a4 | positive control (the a2-pass state) |
| `alpha2-ent-a5` (shared) | 0.10.0a2 / 0.10.0a2 | 0.9.7a5 | enterprise fix alone on reflex a2 |
| `s912-ent-a5` (shared) | 0.9.12 / 0.9.12 (components-core 0.9.10.post1) | 0.9.7a5 | a5 on the previous stable |
| `a3_ent_grid-demo` (MINE) | 0.10.0a3 / 0.10.0a3 (sqlalchemy 2.1.4, greenlet 3.5.6 via `reflex[db]`) | 0.9.7a5 `[mcp]` | ag_grid demo (needs faker/pandas/aiosqlite) |
| `driver` | playwright, Chromium `/opt/pw-browsers/chromium` | | drivers |

Build command for my venv (cwd `$SB`):
```
uv --no-config venv --python 3.12 $SB/envs/a3_ent_grid-demo
uv --no-config pip install --python $SB/envs/a3_ent_grid-demo/bin/python --prerelease=allow 'reflex[db]==0.10.0a3' 'reflex-base==0.10.0a3' 'pydantic<2.14' \
  "$SB/downloads/enterprise_wheel_a5/reflex_enterprise-0.9.7a5-0offline-py3-none-any.whl[mcp]" faker==36.2.2 pandas==2.2.3 aiosqlite
```
greenlet came in through the `db` extra; nothing was added by hand.

## Layout (this directory mirrors `$SB/apps/a3_ent_grid`; `apps/` here = `src/` there)
- **Fixtures**
  - `apps/entv`, `apps/corev` and `apps/probe.py` are the a2-pass verifier fixtures
    (`../../2026-10-07/ent_grid/verification/apps`). Two changes in `rxconfig.py`: the default backend port is 8300, and a guard
    asserts that `reflex` imports from `$SB/envs/$VERIFY_VENV/`.
  - `apps/aggrid_min` is the explorer's minimal repro, with the same guard added.
  - `apps/entr` is the NEW regression-hunt fixture for enterprise#273 (§3).
  - `apps/ag_grid`, `dnd`, `flow` and `mantine` are the a2-pass demo copies (ag_grid includes its `qa_extras.py` QA pages).
    `apps/map` is copied from `/home/user/reflex-enterprise/demos/map`.
- **Driver: `drivers/drive.py`.** This is the verifier's driver. It traps the `window.__reflex` setter, logs `/_event` frames and
  polls grid header/cell counts every 50 ms. My additions:
  - `--app entr` scenarios r1–r5.
  - Badge counts in the 50 ms poll.
  - Per-grid measures: badges, memo badges, tooltip texts, pinned rows, group rows, `.cheap` cells and row texts.
  - `cell_render` trace aggregation: was `window.__reflex` defined when AG Grid invoked a renderer?
  - Tolerant master/detail expansion: records "expand failed" and the error-boundary text when the page crashes.
  - HTTP >= 400 responses and failed requests.
  - The server venv's versions in `server_check.json`.
- **Report helpers**
  - `drivers/summarize.py out [runs...]` builds the entv and corev tables (`out/SUMMARY.md`).
  - `drivers/anomalies.py out/<run>...` lists page errors, non-benign console output, `__reflex` time vs the first grid headers,
    and trace renders.
  - `drivers/grids.py out/<run>` prints entr grid contents.
- **a2-pass drivers (`scripts/`)**
  - Copied unchanged: `probe_aggrid_min.py`, `smoke_routes.py`, `drive_ag_features.py`, `drive_ag_model.py`,
    `probe_state_coldefs.py`, `drive_dnd.py`, `drive_flow.py` and `drive_mantine.py`.
  - Patched: `qa_common.py` (its guard now reads my `pids/current.pgid`).
  - Added: `drive_ag_features_patient.py`, the same driver except that `goto()` also waits up to 30 s for every grid header
    (for dev under load).
- **`bin/`**
  - `start.sh <venv> <app-dir> <log> prod|dev <fp> <bp> [ENV=..]`: setsid, pgid file, polls the frontend and `/ping`, and refuses
    ports outside my range.
  - `stop.sh`: kills the process group and checks that the ports are free.
  - `run.sh <venv> <entv|entr|corev|aggrid_min> prod|dev <port> <out> [driver args] [-- ENV=..]`: refreshes
    `runs/<app>_<venv>` from `src/`, then starts the server, runs the driver and stops the server. The dev backend uses port+5000.
    `RUNSUFFIX=_lazy` selects a separate run dir.
  - `demo.sh <venv> <dnd|flow|mantine|map> prod|dev <label>`: prod on 3318, dev on 3319/8319.
  - `sync_dest.sh` copies to DEST, with JSON compacted by `compact_json.py` and screenshots as small JPEGs.
  - `vers.py` prints the installed versions.

## Rerun (from `$SB/apps/a3_ent_grid`, after copying this directory's `apps/` to `src/` and `bin drivers scripts` alongside)
```
SB=/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad; W=$SB/apps/a3_ent_grid; cd $W
# §1 N-025 matrix (entv s1-s13; s1 runs s1-s5 in one context)
bin/run.sh alpha2-ent    entv prod 3300 entv_alpha2ent_prod --only s1,s11      # positive control: must stay broken
bin/run.sh alpha2-ent-a5 entv prod 3301 entv_alpha2enta5_prod
bin/run.sh alpha2-ent-a5 entv dev  3302 entv_alpha2enta5_dev
bin/run.sh s912-ent-a5   entv prod 3303 entv_s912enta5_prod
bin/run.sh a3-ent        entv prod 3306 entv_a3ent_prod
bin/run.sh a3-ent        entv dev  3307 entv_a3ent_dev
bin/run.sh a3-ent-a4     entv prod 3308 entv_a3enta4_prod --only s1,s11,s8
bin/run.sh a3-ent        aggrid_min prod 3309 aggrid_min_a3ent_prod           # explorer's probe
bin/run.sh a3-ent-a4     aggrid_min prod 3310 aggrid_min_a3enta4_prod
bin/run.sh a3            corev prod 3300 corev_a3_prod --only c1              # core-only: reflex side unchanged
$SB/envs/driver/bin/python drivers/summarize.py out > out/SUMMARY.md
$SB/envs/driver/bin/python drivers/anomalies.py out/entv_a3ent_prod
# §3 regression hunt (entr r1-r5) + lazy flag
bin/run.sh alpha2-ent-a5 entr dev  3304 entr_alpha2enta5_dev
bin/run.sh alpha2-ent-a5 entr prod 3305 entr_alpha2enta5_prod
bin/run.sh a3-ent        entr prod 3311 entr_a3ent_prod
bin/run.sh a3-ent        entr dev  3312 entr_a3ent_dev
bin/run.sh s912-ent-a5   entr prod 3315 entr_s912enta5_prod
RUNSUFFIX=_lazy bin/run.sh a3-ent entv prod 3313 entv_a3ent_prod_lazyflag --only s1,s8,s11,s12 -- REFLEX_FRONTEND_LAZY_BUNDLED_LIBRARIES=true
RUNSUFFIX=_lazy bin/run.sh a3-ent entr prod 3314 entr_a3ent_prod_lazyflag     -- REFLEX_FRONTEND_LAZY_BUNDLED_LIBRARIES=true   # aborts at r2 (page crashed)
RUNSUFFIX=_lazy bin/run.sh a3-ent entr prod 3314 entr_a3ent_prod_lazyflag_r34 --only r3,r4 -- REFLEX_FRONTEND_LAZY_BUNDLED_LIBRARIES=true
$SB/envs/driver/bin/python drivers/anomalies.py out/entr_a3ent_prod ; $SB/envs/driver/bin/python drivers/grids.py out/entr_a3ent_prod
# §4 AG Grid demo (my venv a3_ent_grid-demo; the demo needs a sync DB URL for the ModelWrapper pages)
R=$W/runs/ag_grid_demo; cp -r src/ag_grid $R; (cd $R && CI=true REFLEX_TELEMETRY_ENABLED=false REFLEX_DB_URL=sqlite:///reflex.db $SB/envs/a3_ent_grid-demo/bin/reflex db migrate)
bin/start.sh a3_ent_grid-demo $R logs/ag_grid-prod-a3.log prod 3316 3316 REFLEX_DB_URL=sqlite:///reflex.db
export NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1; D=$SB/envs/driver/bin/python
ROUTES="/ /advanced-serialization /aligned-grids /cell-selection /editable /fill-handle /formatters /integrated-charts /master-detail /model /model-auth /model-ssrm /pivot /qa-grid-memo /qa-grid-props /qa-model-workaround /selected-items /simple-serialization /state-grid /tree"
$D scripts/smoke_routes.py http://localhost:3316 out/ag_prod_a3 ag_grid-smoke a3_ent_grid-demo $ROUTES
$D scripts/probe_state_coldefs.py http://localhost:3316 out/ag_prod_a3 a3_ent_grid-demo prod-a3
$D scripts/drive_ag_features.py http://localhost:3316 out/ag_prod_a3 a3_ent_grid-demo
$D scripts/drive_ag_model.py http://localhost:3316 out/ag_prod_a3 a3_ent_grid-demo $R/reflex.db
bin/stop.sh
# dev: bin/start.sh a3_ent_grid-demo $R logs/ag_grid-dev-a3.log dev 3317 8317 REFLEX_DB_URL=sqlite:///reflex.db ; same drivers on :3317
#      (+ drive_ag_features_patient.py ... pivot,qa_props,qa_memo  and  drive_ag_model.py ... ssrm  after warming /model-ssrm)
# §5 other demos
for a in dnd flow mantine map; do for m in prod dev; do bin/demo.sh a3-ent $a $m a3; done; done
bin/sync_dest.sh
```

## 1. N-025 (entv; `.ag-header-cell` / `.ag-cell` counts inside the grid wrapper, 4 s after the boot frames)
| scenario | a2 pass (a2+a4 prod) | alpha2-ent prod (control) | alpha2-ent-a5 prod | alpha2-ent-a5 dev | s912-ent-a5 prod | **a3-ent prod** | **a3-ent dev** | **a3-ent-a4 prod** |
|---|---|---|---|---|---|---|---|---|
| s1 full load: state / literal grid | 0h0c / 2h6c | 0h0c / 2h6c | 2h6c / 2h6c | 2h6c / 2h6c | 2h6c / 2h6c | **2h6c / 2h6c** | 2h6c / 2h6c | **0h0c** / 2h6c |
| s2 reload | empty | empty | ok | ok | ok | **ok** | ok | **empty** |
| s3 after unrelated-substate event | empty | empty | ok | ok | ok | **ok** | ok | **empty** |
| s4 after same-substate event | recovers | recovers | ok | ok | ok | ok | ok | recovers |
| s5 reload after s4 | ok | ok | ok | ok | ok | ok | ok | ok |
| s6 `/other` → client nav `/` | ok | — | ok | ok | ok | ok | ok | — |
| s7 `/` → `/other` → back | ok | — | ok | ok | ok | ok | ok | — |
| s8 `/memo`: memo-prop / State-in-memo | empty / empty | — | ok / ok | ok / ok | ok / ok | **ok / ok** | ok / ok | **empty / empty** |
| s9 `/onload`: on_load-changed / unchanged | ok / empty | — | ok / ok | ok / ok | ok / ok | **ok / ok** | ok / ok | — |
| s10 second fresh context | empty | — | ok | ok | ok | **ok** | ok | — |
| s11 `/detail` detail-grid headers, state / literal params | `[]` / Count,Value | `[]` / Count,Value | Count,Value ×2 | Count,Value ×2 | Count,Value ×2 | **Count,Value ×2** | Count,Value ×2 | **`[]`** / Count,Value |
| s12 `/renderer` lambda `rx.badge` | 3 badges | — | 3 | 3 | 3 | 3 | 3 | — |
| s13 `/item/1` dynamic route | ok | — | ok | ok | ok | ok | ok | — |

- **Explorer's `aggrid_min` probe.** On a3-ent prod 4/4 PASS: the State grid shows `Make, Price` on load and reload. On a3-ent-a4
  prod it is 2/4: the State grid shows `[]` on load and reload, the a2-pass failure.
- **Errors.** No run had page errors or non-benign console output in the default mode. The only noise was the browser's
  `/favicon.ico` 404 (Playwright's response events do not report it) and the AG Grid licence banners.
- **Server logs.** No tracebacks. Dev logs end with `[ERROR] Unexpected exit from worker-1` because `stop.sh` SIGTERMs the whole
  process group. The same happens on a2, so it is a harness artefact.
- **Boot frames on a3 match a2.** `hydrate_and_load` travels in the socket.io connect auth, and the deltas carry only the root state.
- **Timing.** Grid headers appear about 100 ms after the `__reflex` assignment, for example 481 ms vs 350 ms in s1 on a3-ent prod.
  a5 formats the column defs on the first render; AG Grid paints after its own effects.

Core-only `corev` c1 on a3 prod: Untouched, Other and literal probes stay `NO_REFLEX` (1 render), Touched is `HAS_REFLEX`. This
is identical to a2, so the reflex-side render-before-`__reflex` ordering is unchanged.

## 3. enterprise#273 regression hunt (`apps/entr`, every grid on a prerendered static route)
- **Pages**
  - `/lit` uses literal column defs:
    - a lambda `rx.badge` renderer with `tooltip_field` and `header_tooltip`
    - a lambda `value_formatter` and a lambda `value_getter`
    - `cell_class_rules`
    - a lambda `rx.tooltip(rx.text)` renderer
    - a lambda that returns an `@rx.memo` component (the demo's documented `bundle_library(memo)` pattern)
    - a Python trace renderer (`ArgsFunctionOperation`)

    The page also has a pinned top row and a literal row-grouping grid.
  - `/var` has five Var-valued grids:
    - a State var with JS-string expressions: an arrow-function trace renderer, a string formatter, a `{function}` getter, an
      arrow getter, and a pinned row from State
    - a State var whose DEFAULT holds the Python lambdas
    - `rx.cond(State.flag, <lambda cols>, <plain>)`
    - a computed var
    - row grouping driven by a State var
  - `/detail2` is master/detail. One grid has literal detail params with a lambda `rx.badge` renderer and a trace renderer in the
    detail grid. The other has State detail params with a JS-string renderer and formatter.
  - `/memo2` is an `@rx.memo` grid fed the lambda-holding State var.
- **Scenarios**
  - r1: `/lit` full load, hover, reload.
  - r2: `/var` full load, reload, toggle the cond off and on, bump.
  - r3: `/detail2` expand, then reload and expand again.
  - r4: `/memo2`.
  - r5: client nav `/other` → `/var` → `/lit`.
- **Fixture prerequisite.** `rx.cond` branches that contain Python lambdas need `dynamic.bundle_library("@radix-ui/themes")` at
  import. Without it enterprise raises `Library @radix-ui/themes is not bundled ...` and names that fix. This is creation-time
  behaviour and is not specific to a5.

| run | r1 `/lit` load + reload | r2 `/var` load, reload, toggle, bump | r3 detail expand (load + reload) | r4 `/memo2` | r5 client nav | trace renders without `__reflex` / total (all documents of the run) | page errors |
|---|---|---|---|---|---|---|---|
| a3-ent prod | 6h/24c, 8 badges, pinned row, group row | all 5 grids full; cond 6↔1 cols | Count,Value ×2, 2 badges | 6h/18c, 6 badges | ok | 0 / 80 | 0 |
| a3-ent dev | same | same | same | same | ok | 0 / 160 | 0 |
| alpha2-ent-a5 prod / dev | same | same | same | same | ok | 0 / 80, 0 / 160 | 0 |
| s912-ent-a5 prod (baseline) | same | same | same | same | ok | 0 / 103 | 0 |
| a3-ent prod + lazy flag | **React #130, page crash** | **#130 crash** (driver aborts at toggle) | **#130 crash on expand** | **#130 crash** | — | 0 | — |
| entv on a3-ent prod + lazy flag | s1/s2/s5: #418 from MY probe only, grids ok | — | s11 ok | s8 ok | — | — | s12 `/renderer` **#130 crash** |

- **Values checked in the DOM (a3 prod).** `$1`, `double=2`, `memo:Tesla`, `T:Tesla`, `S:Tesla`, `TESLA`, `1 EUR`, the pinned
  row `PINNED | $99 | 198`, the group row `US (2)` with `sum`, one `.cheap` cell and a tooltip on hover. Identical to 0.9.12+a5.
- **First trace renders vs the `__reflex` assignment.**
  - `/lit` prod: first trace render at 508 ms, `__reflex` assigned at 376 ms.
  - `/var` prod: first trace render at 578 ms, `__reflex` assigned at 374 ms.
- **Pre-existing quirks, identical on 0.9.12 + a5 (not reported):**
  - `rx.badge(params.value)` shows the value JSON-quoted (`"Tesla"`), because the lambda's params are typed generically.
  - AG Grid's dev-only warning `#306 tooltipField is deprecated (v36.2)` appears when the enterprise `tooltip_field` prop is used.
- **Lazy flag.** The #418 on entv pages comes from my ReflexProbe: its text depends on `__reflex`, as noted in the a2 pass. Pages
  without the probe have no #418.

## 4. AG Grid demo (ag_grid + QA pages) on a3-ent, compared with the a2-pass counts
| run | smoke routes | features | model wrapper | state-var column defs probe |
|---|---|---|---|---|
| a2 pass, a2 dev | 20/20 | 46/47 | 24/29 | n/a |
| a2 pass, a2 prod | 20/20 | 39/43 | 24/29 | **3/7** |
| a2 pass, 0.9.12 prod | — | 46/47 | 24/29 | 7/7 |
| **a3-ent prod** | **20/20**, 0 console errors | **46/47** (only `clipboard gold row0->row4`, known driver assumption) | **24/29** (same 5 pre-existing failures) | **7/7** (`/master-detail` State grid, `/qa-grid-memo` memo + 2 ComponentState grids, `/formatters` State tab) |
| **a3-ent dev** | 20/20 | 36/47 on the first pass, but 11 timing fails at load ≈ 25 (see below) | 22/27, then 16/17 on the ssrm rerun (see below) | — |

- **a3 dev features: timing under load, not a bug.**
  - The checks taken right after `goto` (networkidle + 2 s) failed with empty results while the machine load average was 23–30
    (other agents). The final screenshots show the grids fully rendered.
  - The pivot rerun passed.
  - `drive_ag_features_patient.py` (which waits for every grid header) reran pivot, qa_props and qa_memo: 18/18 PASS.
  - Net result: 46/47, as on a2 dev.
- **a3 dev model.**
  - `ssrm: logged-out initial data request made` failed on the cold first visit. After warming `/model-ssrm`, the rerun passed
    16/17; the one failure was the pre-existing filter issue.
  - The other failures are the same pre-existing 4 as a2 and 0.9.12:
    - SSRM and infinite text filters leave blank rows
    - the add dialog's `met` string raises `SQLite DateTime type only accepts Python datetime`, in both prod and dev
  - The 2 dev console errors are `<tr> cannot be a child of <table>` on `/qa-model-workaround`. a2 dev logged them identically.
- **F-001 enterprise half still holds.** `/model`, `/model-auth`, `/model-ssrm` and `/qa-model-workaround` load and serve DB
  rows. SSRM sort, filter request, edit, selection and advanced filter work.
- **Benign.** `/model-auth` logs `AG Grid warning #129 headerCheckbox ... infinite` (demo config, both versions).

## 5. Other enterprise demos on a3-ent (one pass each, dev + prod)
| demo | a3 prod | a3 dev | a2-pass reference | verdict |
|---|---|---|---|---|
| dnd (react-dnd) | 27/27, 0 console/page errors | 27/27 | 27/27 dev + prod | pass |
| flow (React Flow) | 20/22 | 21/22, then 21/22 on rerun | prod 20/22 (same 2 on 0.9.12), dev 22/22 | prod identical; dev failures are load flakes |
| mantine | 23/23 + 1 page error | 23/23 + 1 page error | 23/23 + the same page error (0.9.12 too) | pass (pre-existing) |
| map (leaflet), smoke of 4 routes | 4/4 | 4/4 | not run in the a2 pass | pass (environment noise only) |

- **dnd.** The kanban first load did NOT write the `kanban_data_json` LocalStorage default: only `{"theme": "system"}` was
  present. So #7493 (re-marking client-storage vars dirty at boot) did not bring F-002 back for this LocalStorage pattern. The
  board persists across reload and second tabs.
- **flow prod.** The 2 failures are `index lists 6 flow demos` (driver expectation) and the pre-existing N-026 (controlled edits
  reverted by reload). Both are identical on a2 and 0.9.12 prod.
- **flow dev.** The failing check differed between runs: `add-node-on-edge-drop` first drop on run 1, `intersections` highlight on
  run 2. In run 1 the second drop in the same scenario passed. These are drag-timing flakes at load ≈ 25, not a regression.
- **mantine.** The page error is the pre-existing `Cannot read properties of null (reading 'name')` on `/qa-mantine` (reflex's
  `window.onerror`, §4a of the a2 pass).
- **map.** 54 tile requests to `*.tile.openstreetmap.org` failed with `net::ERR_TUNNEL_CONNECTION_FAILED` because the sandbox proxy
  blocks them. The routes render with their controls. No server tracebacks.

## Not covered
- `header_component` / `tooltip_component` given as Python lambdas (only `header_tooltip`/`tooltip_field` and an `rx.tooltip` cell).
- A Redis state manager.
- a3-ent-a4 on the entr fixture: the Var-valued grids would be empty there, as in N-025.
- A 0.9.12 baseline for the demo flakes (the failing checks varied, so the flakes are environmental).
