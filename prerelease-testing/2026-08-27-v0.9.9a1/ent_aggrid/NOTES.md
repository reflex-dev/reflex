# ent_aggrid — reflex-enterprise 0.9.4 ag_grid demo vs reflex 0.9.9a1

Agent cluster: `ent_aggrid`. Tested 2026-08-28.
Packages (all from PyPI): `reflex-enterprise==0.9.4` against `reflex==0.9.9a1`
(reflex-base 0.9.9a1) and baseline `reflex==0.9.8` (reflex-base 0.9.8).
Demo source: `/home/user/reflex-enterprise/demos/ag_grid` (read-only reference; copied here).

## Layout of this artifact dir

- `demo_a1/` — demo copy run against reflex 0.9.9a1 (contains the two demo patches
  described below plus the "formatters page disabled" patch in `ag_grid/ag_grid.py`)
- `demo_098/` — demo copy run against reflex 0.9.8 (same two demo patches, formatters ENABLED)
- `minimal/` — minimal repro app (one `rxe.ag_grid`; `REPRO_LAMBDA=1` adds one
  lambda `cell_renderer` column that reproduces the 0.9.9a1 compile crash)
- `drive_aggrid.py` / `drive_minimal.py` — Playwright drivers
- `probe_pages.py` / `probe_coldefs.py` — offline per-page / per-column-def crash probes
- `logs/` — full server logs for every run
- `artifacts/` — extracted tracebacks, package.json snapshots + diff
- `shots_098/`, `shots_a1/`, `shots_minimal/` — screenshots + `report.json`
  (per-route actions, console errors/warnings, failed network requests)

## Setup / rerun instructions

```bash
cd demo_a1   # or demo_098
uv venv venv --python 3.11
uv pip install --python venv/bin/python --prerelease=allow \
    'reflex==0.9.9a1' 'reflex-enterprise==0.9.4' -r requirements.txt   # 0.9.8 for baseline
# DB init (alembic.ini was pointed at sqlite:///reflex.db; placeholder URL upstream):
./venv/bin/alembic upgrade head
# rxe demands login; CI=1 bypasses AppEnterprise._check_login()'s exit():
CI=1 REFLEX_TELEMETRY_ENABLED=false ./venv/bin/reflex run --loglevel debug \
    --frontend-port 3300 --backend-port 8300   # 3301/8301 used for 0.9.8
# drive (Playwright, chromium at /opt/pw-browsers/chromium):
NO_PROXY=localhost,127.0.0.1 python drive_aggrid.py http://localhost:3300 shots_out
```

Minimal repro (no DB needed):

```bash
cd minimal
CI=1 REPRO_LAMBDA=1 REFLEX_TELEMETRY_ENABLED=false <venv>/bin/reflex run \
    --loglevel debug --frontend-port 3302 --backend-port 8302
# on 0.9.9a1: exits during "Compiling" with
#   reflex_base.utils.exceptions.VarAttributeError: Attribute _cached_get_all_var_data not found.
# on 0.9.8: runs; lambda column renders (shots_minimal/min_lambda_098.png)
# without REPRO_LAMBDA: runs fine on BOTH versions (plain grid, sort works).
```

Offline probes (no server, seconds instead of minutes):

```bash
cd demo_a1 && CI=1 PYTHONPATH=$PWD ./venv/bin/python ../probe_pages.py    # which page crashes
cd demo_a1 && CI=1 PYTHONPATH=$PWD ./venv/bin/python ../probe_coldefs.py  # which column def crashes
```

## FINDINGS

### 1. REGRESSION (HIGH): lambda/python-function grid props crash app compile on 0.9.9a1 — FINDING-001 end-to-end confirmation

- Root cause is exactly FINDING-001: `reflex_enterprise/vars.py:143`
  (`bundled_libraries = set(dynamic.bundled_libraries)` inside
  `LiteralLambdaVar._validate_and_extend_return_expr`) reads
  `reflex.components.dynamic.bundled_libraries`, removed by reflex-base 0.9.9a1 (#6382).
- BUT the user never sees that AttributeError. The read happens inside the computation of
  `CachedVarOperation._cached_get_all_var_data` (a custom `cached_property`); the
  AttributeError escaping a descriptor `__get__` makes Python fall back to
  `Var.__getattr__`, which raises
  `reflex_base.utils.exceptions.VarAttributeError: Attribute _cached_get_all_var_data not found.`
  with NO chained cause. The real error is completely masked (see finding 2).
  Full tracebacks: `artifacts/traceback_demo_a1_masked_varattributeerror.txt` (demo),
  `artifacts/traceback_minimal_a1.txt` (minimal app).
- Trigger granularity, established with `probe_coldefs.py`: a column def whose
  `cell_renderer`/`value_formatter` is a python callable AND whose compiled return
  expression carries imports:
  - `cell_renderer=lambda params: rx.text(...)` — CRASH (component import)
  - `cell_renderer=lambda params: row_counter(...)` (`@rx.memo`) — CRASH
  - `value_formatter=flag_formatter` (uses `Var.create({...}).get(...)` whose JS
    helper needs an import) — CRASH
  - `value_formatter=lambda params: round(params.value.to(float), 4)` — OK (no imports)
  - `value_formatter=currency_formatter` (string ops only) — OK
  - plain-string / FunctionStringVar formatters and getters — OK
- Only 1 of 17 demo pages (`/formatters`) contains crashing constructs, but ONE bad page
  aborts the WHOLE app compile, so the demo as a whole is dead on 0.9.9a1.
- A/B proof with byte-identical app code (after the demo fixes of finding 3):
  0.9.8 compiles and all 17 routes work end-to-end in Chromium; 0.9.9a1 exits at
  "Compile pages" with the masked VarAttributeError.
- With the formatters page disabled (`demo_a1/ag_grid/ag_grid.py`), the OTHER 16 routes
  work on 0.9.9a1 exactly like on 0.9.8 (same row counts, sorting, cell editing incl.
  on_cell_value_changed toast, master-detail expand, tree expand, selection checkboxes,
  state-driven column/data loading, grid-state serialization, pivot, integrated charts;
  compare `shots_a1/report.json` vs `shots_098/report.json`).
- A trivial `rxe.App` + `rxe.ag_grid` with no python-callable props works fine on
  0.9.9a1 end-to-end (`shots_minimal/min_plain_a1.png`), so the breakage is confined to
  the LambdaVar path — but that path is core to ag-grid's formatter/renderer story
  (and is also used by map/dnd per FINDING-001).

### 2. ANOMALY (MEDIUM, reflex-base, not new in 0.9.9a1): CachedVarOperation masks AttributeError raised inside cached computations

- Any `AttributeError` raised while computing `_cached_get_all_var_data` /
  `_cached_var_name` (custom `cached_property` in `reflex_base/vars/base.py`) is
  swallowed by the descriptor protocol and re-surfaced as
  `VarAttributeError: Attribute _cached_get_all_var_data not found.` with no `__cause__`.
  Diagnosing finding 1 required patching `cached_property.__get__` to see the real error.
- Suggested direction (not applied): catch `AttributeError` inside
  `cached_property.__get__` (or the cached function wrapper) and re-raise as
  `RuntimeError`/chained error so real failures aren't converted into bogus
  attribute-lookup misses.

### 3. DEMO BUGS (independent of 0.9.9a1 — demo is broken on reflex 0.9.8 too, as shipped)

The shipped demo crashes at compile on PLAIN reflex 0.9.8 + rxe 0.9.4:
`ValueError: Library $/app_components/ag_grid/formatters is not bundled.`
(traceback: `artifacts/traceback_demo_098_shipped_bundle_path.txt`). Two distinct causes:

- a. `formatters.py` line 16 bundles `"$/utils/components"`, but since reflex 0.9.8
  `@rx.memo` components are emitted under `$/app_components/<module path>`, so the
  memo renderer's real library is never bundled -> the compile ValueError above.
  Worse, keeping the stale path bundled injects `import '$/utils/components'` into
  `.web/app/root.jsx`, which vite cannot resolve -> HTTP 500 on EVERY route
  (observed in the intermediate run where both paths were bundled at import time).
- b. Fix applied in both copies (`ag_grid/formatters.py`): `_bundle_renderer_libraries()`
  bundles `$/app_components/ag_grid/formatters` (stale path dropped), called BOTH at
  import time and from `formatter_page()`. The page-eval call is belt-and-suspenders:
  `compile_app()` (reflex/compiler/compiler.py:1202 on 0.9.8) calls
  `reset_bundled_libraries()` after the app module import and before compiling pages,
  wiping import-time `bundle_library` calls from the live list (verified: the entry is
  gone from `dynamic.bundled_libraries` after reset). In practice serializer/var caching
  can let an import-time-validated lambda pass anyway (offline probe
  "VALIDATION PASSED" after a manual reset), so the exact failure boundary is fuzzy —
  but rxe's own error-message advice (import-time `bundle_library`) is unreliable on
  reflex >= 0.9.8.
- c. Related runtime anomaly on 0.9.8: with the compile fixed, the backend worker logs
  `[Reflex Backend Exception] ... ValueError: Library @radix-ui/themes is not bundled`
  whenever it serializes `FormatterState.cols_defs` (state var holding lambdas) during
  event processing — the worker process never runs `compile_app`, so the radix plugin's
  `bundle_library("@radix-ui/themes")` never executed there
  (`artifacts/backend_exception_098_state_lambda_serialization.txt`). The
  formatters page still renders (Inline tab), but the "State" tab's column defs never
  reach the client. Same class of bundled-libraries state-desync, worth an rxe issue.

### 4. BASELINE BUG (both versions, "broken anyway"): ModelWrapper data endpoint 404 — `?` percent-encoded

- `/model`, `/model-auth`, `/model-ssrm` grids never load rows on 0.9.8 NOR 0.9.9a1:
  every datasource fetch goes to
  `http://localhost:<backend>/abstract-wrapper-data%3FstartRow=0&endRow=50&...` (note `%3F`)
  and gets HTTP 404. Root cause in `reflex_enterprise/utils.py:get_backend_url`: it
  assigns `path + "?query"` to `URL.pathname`; per the URL spec the `pathname` setter
  percent-encodes `?`, so the query string becomes part of the path and Starlette's
  `/abstract-wrapper-data` route never matches.
- Identical failure signature on both reflex versions (see `failed` arrays for those
  routes in `shots_098/report.json` and `shots_a1/report.json`) => NOT a 0.9.9a1
  regression; rxe 0.9.4's infinite-row ModelWrapper appears broken with any
  current reflex. (DB was initialized and reachable; the request never reaches the route.)

### 5. Environment quirks (context, not bugs)

- rxe requires login: `AppEnterprise._check_login()` calls `exit()` when tier is
  anonymous. `CI=1` (or backend-only) bypasses. All runs here used `CI=1`.
- `alembic.ini` ships with placeholder `sqlalchemy.url`; pointed at `sqlite:///reflex.db`
  and ran `alembic upgrade head` (creates `friend` table). The DB starts empty; model
  pages would show 0 rows even without finding 4.
- AG Grid Enterprise trial banner ("License Key Not Found") is printed as console
  ERRORS on every enterprise-feature page (14-42 per page) — benign/expected without
  a license key, on both versions.
- Deprecation warnings on both versions: `@rx.memo` without annotations
  (formatters.py row_counter), `rx.Model` (used by model wrapper demos),
  strings in `disable_plugins`, implicit Radix themes; on 0.9.9a1 additionally
  rxe's use of `console.error`/`console.info` is flagged deprecated.
- `/editable` toast count differed (baseline 2 vs a1 1) — sonner renders a
  stacked duplicate intermittently; cell edit + state update itself identical.

## package.json (frontend deps) 0.9.8 vs 0.9.9a1

`artifacts/package_098.json` vs `artifacts/package_a1.json`, diff in
`artifacts/package_json.diff`. Framework-level changes: react-router 7.18.2 -> 8.3.0
(react-router-dom dropped), vite 8.0.16 -> 8.2.0, postcss override removed.
(moment/react-moment absent from the a1 build only because the formatters page — the
sole rx.moment user — was disabled there.)

## Test matrix summary

| Check | 0.9.8 | 0.9.9a1 |
|---|---|---|
| shipped demo compile | FAIL (ValueError: $/app_components/ag_grid/formatters not bundled) | FAIL (masked VarAttributeError) |
| demo + bundling fixes compile | PASS | FAIL (masked VarAttributeError) — REGRESSION |
| 16 non-formatter routes E2E | PASS (all interactions) | PASS (formatters disabled; identical behavior) |
| /formatters E2E (fixed demo) | PASS (all 3 def styles, memo renderer clickable) | impossible (compile fails) |
| /model, /model-auth, /model-ssrm data load | FAIL (404 %3F) | FAIL (404 %3F) — broken anyway |
| minimal plain rxe.ag_grid | PASS | PASS |
| minimal + lambda cell_renderer | PASS | FAIL at compile — REGRESSION (minimal trigger) |
