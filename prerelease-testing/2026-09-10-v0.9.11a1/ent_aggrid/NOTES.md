# ent_aggrid — reflex-enterprise 0.9.5 ag_grid demos vs reflex 0.9.11a1

Cluster: `ent_aggrid`. Tested 2026-09-10/11.
All packages from PyPI in isolated uv venvs (never from a checkout).

| stack | reflex | reflex-base | reflex-enterprise | radix | moment | code | core |
|---|---|---|---|---|---|---|---|
| **under test** | 0.9.11a1 | 0.9.11a1 | 0.9.5 | 0.9.9a1 | 0.9.4a1 | 0.9.5a1 | 0.9.9 |
| **baseline**   | 0.9.10.post2 | 0.9.10.post2 | 0.9.5 | 0.9.8 | 0.9.3 | 0.9.4 | 0.9.9 |

Apps under test:

- `demo_a1/` — copy of `/home/user/reflex-enterprise/demos/ag_grid` (repo HEAD 2026-09-03),
  17 routes, run against reflex 0.9.11a1. One patch applied, see "Demo patch" below.
- `demo_0910/` — byte-identical copy run against reflex 0.9.10.post2 (baseline).
- `finance_a1/` — copy of `/home/user/reflex-dev/reflex-examples/ag_grid_finance`,
  run against reflex 0.9.11a1. yfinance is blocked by the egress proxy here, so the copy
  substitutes a deterministic offline data generator (see "Finance patch").
- `finance_0910/` — same copy, reflex 0.9.10.post2 baseline.

## Headline result

**No regression.** Every one of the 17 ag_grid demo routes behaves *identically* on
reflex 0.9.11a1 and reflex 0.9.10.post2, in dev **and** in prod (`shots/*/report.json`
action lists diff to zero on both pairs). The `ag_grid_finance` example likewise behaves
identically on both.

**The 0.9.9a1 enterprise breakage is fixed.** The LambdaVar / python-callable
renderer+formatter path that was dead in 0.9.9a1 (2026-08-27 FINDING-001/021/022) now
works end-to-end: `/formatters` renders flag/currency/percent formatters, the purple
monospace `rx.text` cell renderer, the tooltip renderer, the `@rx.memo` `row_counter`
button (clickable, increments, live `rx.moment` duration) and the `@rxe.static`
"Raw Data" dialog, in all three column-def styles (Inline / State / API tab).
See `shots/dev_a1/formatters.png`, `formatters_tab_state.png`, `formatters_rawdialog.png`.

It is fixed **twice over**, independently:

- reflex 0.9.11a1 restored `reflex.components.dynamic.bundled_libraries` and
  `reflex.page.DECORATED_PAGES` as deprecation shims (`console.deprecate`, removal 1.0);
- reflex-enterprise 0.9.5 (#219) added `reflex_enterprise.vars.get_bundled_libraries()`
  which reads `RegistrationContext.ensure_context().bundled_libraries` and falls back to
  the old module attribute.

## Status of every 2026-08-27 enterprise finding

| 0.9.9a1 finding | status on reflex 0.9.11a1 + rxe 0.9.5 | evidence |
|---|---|---|
| FINDING-001 `dynamic.bundled_libraries` removed | **FIXED** (deprecation shim in reflex; rxe also fixed independently) | `scripts/probe_legacy_apis.py` |
| FINDING-021 ag-grid python-callable renderer/formatter crashes compile | **FIXED** — `/formatters` fully working, all 3 tab styles | `shots/dev_a1/formatters*.png` |
| FINDING-022 non-static LambdaVar prop with imports crashes | **FIXED** — `LiteralLambdaVar.create()` succeeds for component / dict-get / no-import returns | `scripts/probe_legacy_apis.py` |
| FINDING-023 `reflex.page.DECORATED_PAGES` removed | **FIXED** — shim returns the defaultdict with a deprecation warning | `scripts/probe_legacy_apis.py` |
| FINDING-024 `CachedVarOperation` masks AttributeError as bogus `VarAttributeError` | **NOT FIXED** — identical on 0.9.11a1 and 0.9.10.post2 | `scripts/probe_masked_attrerror.py` (ISSUE 3) |
| FINDING-025 shipped rxe ag_grid demo bundles the stale `$/utils/components` | **NOT FIXED** — demo HEAD still crashes at compile on both versions | `logs/run_0910_shipped_unpatched.log`, `artifacts/traceback_shipped_demo_a1_bundle_path.txt` (ISSUE 1) |
| FINDING-026 `/​_reflex/cookies/sync` 404 (OIDC demo) | not in this cluster (ent_misc) — not retested here | — |
| FINDING-029 rxe error paths call deprecated `console.*` | **NOT FIXED** — `console.info` (`app.py:154`) fires on every dev/prod start, `console.error` (`utils.py:119` / `app.py:120`) on the login and prod gates | `logs/run_a1_dev.log:75,215` (ISSUE 6) |

## Setup / exact rerun commands

Everything below assumes `SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad`
and `A=$SB/apps/ent_aggrid`, and that **no `uv pip install` is ever run from `/home/user/reflex`**
(the checkout's `[tool.uv] exclude-newer` silently filters the alphas).

### ag_grid demo (17 routes)

```bash
mkdir -p $A && cp -r /home/user/reflex-enterprise/demos/ag_grid $A/demo_a1
cd $A/demo_a1
grep -v '^reflex' requirements.txt > requirements_norx.txt     # drop the demo's reflex pins
uv venv $A/venv_a1 --python 3.11
UV_HTTP_TIMEOUT=180 uv pip install --python $A/venv_a1/bin/python --prerelease=allow \
    'reflex==0.9.11a1' 'reflex-enterprise==0.9.5' -r requirements_norx.txt
# (uv times out against files.pythonhosted.org fairly often here; just rerun the install)

# DB: alembic.ini ships a placeholder URL
sed -i 's|^sqlalchemy.url = driver://user:pass@localhost/dbname|sqlalchemy.url = sqlite:///reflex.db|' alembic.ini
CI=1 $A/venv_a1/bin/alembic upgrade head
$A/venv_a1/bin/python $A/scripts/seed_db.py 200      # demo ships an empty DB

# apply the demo patch described below, then:
CI=1 REFLEX_TELEMETRY_ENABLED=false $A/venv_a1/bin/reflex run --loglevel debug \
    --frontend-port 5100 --backend-port 9500 > $A/logs/run_a1_dev.log 2>&1 &

NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python $A/scripts/drive_aggrid.py \
    http://localhost:5100 $A/shots/dev_a1          # 17 routes, screenshots + report.json
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python $A/scripts/drive_deep.py \
    http://localhost:5100 $A/shots/dev_a1          # charts / fill handle / aligned / editable / selection
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python $A/scripts/drive_hydrate2.py \
    http://localhost:5100 $A/shots/dev_a1          # ISSUE 2 repro
```

Prod (single port for frontend AND backend; `CI=1` does **not** bypass the prod gate,
`APP_HARNESS_FLAG=1` does — `reflex_enterprise/utils.py::is_in_app_harness()`):

```bash
CI=1 APP_HARNESS_FLAG=1 REFLEX_TELEMETRY_ENABLED=false $A/venv_a1/bin/reflex run --env prod \
    --loglevel debug --frontend-port 5101 --backend-port 5101 > $A/logs/run_a1_prod.log 2>&1 &
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python $A/scripts/drive_aggrid.py \
    http://localhost:5101 $A/shots/prod_a1
```

Baseline: same steps with `uv pip install --python $A/venv_0910/bin/python
'reflex==0.9.10.post2' 'reflex-enterprise==0.9.5' -r requirements_norx.txt`
(**no** `--prerelease=allow`, so the stable radix/moment/code sub-packages are used),
ports 5102/9502 (dev) and 5105/5105 (prod).

### ag_grid_finance (reflex-examples)

```bash
cp -r /home/user/reflex-dev/reflex-examples/ag_grid_finance $A/finance_a1
cd $A/finance_a1 && grep -v '^reflex' requirements.txt > requirements_norx.txt
uv venv $A/venv_fin --python 3.11
UV_HTTP_TIMEOUT=180 uv pip install --python $A/venv_fin/bin/python --prerelease=allow \
    'reflex==0.9.11a1' 'reflex-enterprise==0.9.5' -r requirements_norx.txt pandas
# apply the finance patch (see below), then
CI=1 REFLEX_TELEMETRY_ENABLED=false $A/venv_fin/bin/reflex run --loglevel debug \
    --frontend-port 5103 --backend-port 9503 > $A/logs/run_fin_a1_dev.log 2>&1 &
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python $A/scripts/drive_finance.py \
    http://localhost:5103 $A/shots/fin_a1
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python $A/scripts/drive_finance_sel.py \
    http://localhost:5103 $A/shots/fin_a1
```

Baseline used `venv_0910` (+ `yfinance==0.2.54`) on ports 5104/9504.

### Offline probes (seconds, no server)

```bash
cd $A     # NEVER /home/user/reflex — it shadows the installed reflex package
$A/venv_a1/bin/python $A/scripts/probe_legacy_apis.py      # FINDING-001/021/022/023 status
$A/venv_a1/bin/python $A/scripts/probe_masked_attrerror.py # FINDING-024 status (ISSUE 3)
$A/venv_0910/bin/python $A/scripts/probe_masked_attrerror.py  # same on the baseline
```

## Patches applied to the copied apps (and why)

### Demo patch — `demo_a1/ag_grid/formatters.py` and `demo_0910/ag_grid/formatters.py`

The shipped demo does `dynamic.bundle_library("$/utils/components")` at line 16. That path
has not existed since reflex 0.9.8 (memo components now compile to
`$/app_components/<module path>`), so the unpatched demo **cannot start on any current
reflex** — see ISSUE 1. The patch replaces it with a helper that bundles
`$/app_components/ag_grid/formatters` and is called **both at import time and from
`formatter_page()`**; the page-eval call is required because `compile_app()` calls
`reset_bundled_libraries()` *after* importing the app module
(`reflex/compiler/compiler.py:1212` in 0.9.11a1), which wipes any import-time registration.
Import-time-only is not enough — verified, it still fails:
`ValueError: Library $/app_components/ag_grid/formatters is not bundled`.
The same patch is applied to both copies, so the A/B is byte-identical app code.

### Finance patch — `finance_a1/ag_grid_finance/ag_grid_finance.py` (and the 0910 copy)

The egress proxy returns `403 Forbidden` for `fc.yahoo.com`, so `yf.download()` returns an
empty DataFrame and the app has nothing to grid. `_offline_download()` produces a
deterministic DataFrame with exactly the shape yfinance returns (MultiIndex
`(ticker, field)` columns, `DatetimeIndex` named `Date`). Nothing else is changed; the
`import yfinance` is kept so the dependency is still exercised. **Every finance result
below therefore uses synthetic prices**, but the grid/pagination/filter/sort/theme/state
paths are the real ones.

### Test-harness only

- `CI=1` — bypasses `AppEnterprise._check_login()`, which otherwise `exit()`s.
- `APP_HARNESS_FLAG=1` — bypasses `reflex_enterprise/utils.py::enforce_tier()` for
  `reflex run --env prod`, which otherwise exits with
  "requires a paid Reflex subscription ... You are currently logged out".
- `scripts/seed_db.py` — inserts N fake `friend` rows; the demo ships an empty DB.

## Results table

R = reflex 0.9.11a1 + rxe 0.9.5; B = reflex 0.9.10.post2 + rxe 0.9.5.

| # | Check | dev R | dev B | prod R | prod B | note |
|---|---|---|---|---|---|---|
| 1 | shipped (unpatched) demo compiles | FAIL | FAIL | — | — | ISSUE 1, both versions |
| 2 | patched demo compiles + serves | PASS | PASS | PASS | PASS | |
| 3 | `/` index: 17 demo cards + links | PASS | PASS | PASS | PASS | |
| 4 | `/formatters` python-callable renderers + formatters | PASS | PASS | PASS | PASS | FINDING-021 fixed |
| 5 | `/formatters` `@rx.memo` row-counter button click → state | PASS | PASS | PASS | PASS | 0 → 1 → 2 |
| 6 | `/formatters` `@rxe.static` "Raw Data" dialog | PASS | PASS | PASS | PASS | |
| 7 | `/formatters` Inline / State / API tabs agree | PASS | PASS | PASS | PASS | incl. `api.set_grid_option("column_defs", …)` |
| 8 | `/editable` cell edit → `on_cell_value_changed` → toast | PASS | PASS | PASS | PASS | dev also raises an error toast, ISSUE 2 |
| 9 | `/master-detail` expand → detail row | PASS | PASS | PASS | PASS | |
| 10 | `/tree` group expand (5 → 10 rows) | PASS | PASS | PASS | PASS | |
| 11 | `/pivot` pivot columns + sidebar tool panel | PASS | PASS | PASS | PASS | |
| 12 | `/selected-items` checkbox / Select All (0 → 128 → 0) | PASS | PASS | PASS | PASS | |
| 13 | `/cell-selection` range select echoed to state | PASS | PASS | PASS | PASS | |
| 14 | `/fill-handle` drag fill (8,6,4,1 → 8,8,8,8) | PASS | PASS | n/t | n/t | |
| 15 | `/aligned-grids` horizontal scroll sync between grids | PASS | n/t | n/t | n/t | `scripts/probe_aligned.py`: grid0 → 200 moves grid1 → 200 |
| 16 | `/state-grid` "Load columns"/"Load data" (0 → 26 rows) | PASS | PASS | PASS | PASS | |
| 17 | `/simple-serialization`, `/advanced-serialization` grid state round-trip | PASS | PASS | PASS | PASS | |
| 18 | `/integrated-charts` grid + range + context menu | PASS | PASS | PASS | PASS | chart itself does not render, ISSUE 4 |
| 19 | `/model`, `/model-auth`, `/model-ssrm` datasource load | FAIL | FAIL | FAIL | FAIL | ISSUE 5, both versions |
| 20 | generic sort / floating filter on every route | PASS | PASS | PASS | PASS | |
| 21 | hydrate delta reaches the client (session state survives reload) | **FAIL** | **FAIL** | PASS | PASS | ISSUE 2 — dev only, both versions |
| 22 | hot reload of a demo page source (`header_name` change) | PASS | n/t | — | — | header flips to "HMR Name"; error toast also disappears afterwards |
| 23 | finance: initial render + "Fetch Latest Data" (645 rows) | PASS | PASS | n/t | n/t | |
| 24 | finance: pagination (page size 20/50, next page) | PASS | PASS | n/t | n/t | "1 to 20 of 645", "Page 2 of 33" |
| 25 | finance: column filter (ticker = AAPL) | PASS | PASS | n/t | n/t | |
| 26 | finance: sort by Close | PASS | PASS | n/t | n/t | |
| 27 | finance: theme switch quartz/balham/alpine/material | PASS | PASS | n/t | n/t | four visually distinct screenshots |
| 28 | finance: row selection → `on_selection_changed` → recharts chart | **FAIL** | **FAIL** | n/t | n/t | ISSUE 7, both versions |
| 29 | `bundled_libraries` / `DECORATED_PAGES` compat shims | PASS | n/a | — | — | new in 0.9.11a1 |
| 30 | AttributeError inside a cached var computation is diagnosable | **FAIL** | **FAIL** | — | — | ISSUE 3, both versions |

`n/t` = not tested in that configuration.

## Issues

Every issue below was checked against reflex 0.9.10.post2 with the same
reflex-enterprise 0.9.5 — **none of them is a regression of this release train.**

### ISSUE 1 (MEDIUM, downstream: reflex-enterprise demo, pre-existing) — shipped ag_grid demo cannot start: stale `$/utils/components` bundle path

`demos/ag_grid/ag_grid/formatters.py:16` calls
`dynamic.bundle_library("$/utils/components")`. Since reflex 0.9.8 an `@rx.memo`
component compiles to `$/app_components/<module path>`, so `row_counter`'s real library
(`$/app_components/ag_grid/formatters`) is never bundled and rxe's LambdaVar validation
aborts the compile.

Repro (fresh clone of the demo, no patch):

```bash
cp -r /home/user/reflex-enterprise/demos/ag_grid /tmp/x && cd /tmp/x
uv venv v --python 3.11
uv pip install --python v/bin/python --prerelease=allow 'reflex==0.9.11a1' \
    'reflex-enterprise==0.9.5' faker==36.2.2 pandas==2.2.3 aiosqlite greenlet
sed -i 's|^sqlalchemy.url = .*|sqlalchemy.url = sqlite:///reflex.db|' alembic.ini
CI=1 v/bin/alembic upgrade head
CI=1 REFLEX_TELEMETRY_ENABLED=false v/bin/reflex run --frontend-port 5100 --backend-port 9500
# exit 1: ValueError: Library $/app_components/ag_grid/formatters is not bundled.
```

Evidence: `artifacts/traceback_shipped_demo_a1_bundle_path.txt` (0.9.11a1),
`logs/run_0910_shipped_unpatched.log` (identical on 0.9.10.post2).
Note the shipped remedy in rxe's own error message (import-time `bundle_library`) is
**not sufficient** — `compile_app()` resets the list after importing the app module
(`reflex/compiler/compiler.py:1212`), so the call must also run at page-eval time.
This is 2026-08-27 FINDING-025, still open, and it means nobody can run the flagship
enterprise ag-grid demo out of the box.

### ISSUE 2 (HIGH, downstream root cause + framework-side contributor, pre-existing) — dev mode: the whole hydrate delta is dropped on every page of an rxe app that stores python callables in a state var, and a raw internal error is shown to the user

In `reflex run` (dev) the granian worker skips `compile_app()` (the `.nocompile` marker),
so the radix plugin's `bundle_library("@radix-ui/themes")` never executes in that process.
When the worker then serializes `FormatterState.cols_defs` (a root-level `list[dict]`
state var holding python lambdas) for the hydrate delta, rxe's
`LiteralLambdaVar._validate_and_extend_return_expr` (`reflex_enterprise/vars.py:166`)
raises `ValueError: Library @radix-ui/themes is not bundled` inside
`emit_delta → _sio_dumps`. Consequences:

1. The delta never reaches the browser — **once per page load, on all 17 routes**
   (17 `[Reflex Backend Exception]` blocks per full sweep, `logs/run_a1_dev.log`).
2. Session state silently reverts in the UI. Repro: `scripts/drive_hydrate2.py`
   — click the `/formatters` row-counter 3 times (UI shows 3), reload → UI shows `0 (∞)`,
   click once → jumps to **4**, proving the server kept the value and only the delta was lost.
3. The user is shown the raw internal error. `shots/dev_a1/hmr_before.png` is a plain
   load of `/editable` with a red panel reading
   "An error occurred. ValueError: Library @radix-ui/themes is not bundled. Use
   `from reflex.components.dynamic import bundle_library; bundle_library('@radix-ui/themes')
   to enable it it." (note also the doubled "it it" typo in rxe's message).

Prod is unaffected (the prod worker compiles, so the list is populated): 0 exceptions,
and the reload test returns 3. A dev hot reload also cures it for the rest of the session.

Repro from scratch: follow "Setup" for `demo_a1`, then
`NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python $A/scripts/drive_hydrate2.py http://localhost:5100 out`
and `grep -c 'Reflex Backend Exception' $A/logs/run_a1_dev.log`.

Evidence: `artifacts/backend_exception_hydrate_delta_a1.txt` (full traceback),
`logs/run_a1_dev.log` (17 blocks) vs `logs/run_0910_dev.log` (17 identical blocks),
`logs/run_a1_prod.log` / `logs/run_0910_prod.log` (0 blocks),
`shots/dev_a1/hydrate_report2.json`, `shots/prod_a1/hydrate_report2.json`,
`shots/dev_a1/hmr_before.png`.

Attribution: the validation and the message belong to reflex-enterprise, and rxe should
not validate against a list it knows is process-local. But reflex owns the two halves that
make it fatal: (a) `bundled_libraries` is populated only in processes that run
`compile_app()`, so the frontend bundle and the serving worker's registry are permanently
out of sync in dev; (b) a single unserializable var takes down the *entire* delta for the
session with no client-side recovery. Worth fixing on the reflex side even though it is
not new.

### ISSUE 3 (MEDIUM, reflex-base, pre-existing) — `AttributeError` raised inside a cached var computation is still reported as a bogus `VarAttributeError`

2026-08-27 FINDING-024 is unchanged in 0.9.11a1. Any `AttributeError` escaping a
`CachedVarOperation` cached computation is discarded by Python's attribute machinery and
re-raised by `Var.__getattr__` as
`VarAttributeError: Attribute _cached_get_all_var_data not found.` with
`__cause__ is None` — the real error is invisible.

Repro: `cd $A && $A/venv_a1/bin/python $A/scripts/probe_masked_attrerror.py`
(a `CachedVarOperation` subclass whose `_cached_get_all_var_data` raises
`AttributeError("REAL ERROR: ...")`). Output on 0.9.11a1 **and** on 0.9.10.post2:
`reflex_base.utils.exceptions.VarAttributeError: Attribute _cached_get_all_var_data not found.`
raised at `reflex_base/vars/base.py:1471` via `base.py:2120`, no cause, no mention of the
real error. This is exactly what made 0.9.9a1's headline enterprise breakage
undebuggable; the shims fixed that instance, not the masking.

### ISSUE 4 (LOW, downstream: reflex-enterprise pins, pre-existing) — `/integrated-charts` cannot draw a chart: ag-grid 34.3.1 pinned against ag-charts 11.2.4

`.web/package.json` gets `ag-grid-*@34.3.1` with `ag-charts-enterprise@11.2.4`. AG Grid
itself rejects the pair on every load of `/integrated-charts`:

```
AG Grid: AG Grid version 34.3.1 and AG Charts version 11.2.4 is not supported.
AG Grid version 34.3.x should be used with AG Chart 12.3.x.
```

The grid, the cell range and the "Chart Range" context-menu entry all work, but choosing a
chart produces the page error `Cannot assign to read only property 'api' of object '#<Object>'`
and no chart element is created (`chart_wrappers = 0`).

Repro: `scripts/drive_deep.py <base> <shots>` section `integrated_charts`
(select a cell range, right-click, hover "Chart Range" → "Column" → "Grouped").
Evidence: `shots/dev_a1/deep_report.json`, `shots/dev_a1/charts_01_contextmenu.png`,
`charts_03_after_chart.png`. Identical pins and identical failure on 0.9.10.post2
(`shots/dev_0910/deep_report.json`) and in the 2026-08-27 artifacts
(`.../2026-08-27-v0.9.9a1/ent_aggrid/artifacts/package_a1.json`), so this predates both
trains. Fix belongs in reflex-enterprise's `ag_grid` package pins.

### ISSUE 5 (MEDIUM, downstream: reflex-enterprise, pre-existing) — `ModelWrapper` datasource URL percent-encodes `?`, every row fetch 404s

`/model`, `/model-auth` and `/model-ssrm` never load a row. Every datasource request goes to

```
http://localhost:9500/abstract-wrapper-data%3FstartRow=0&endRow=50&sortModel=%5B%5D&...
```

(note `%3F`) and returns 404. Root cause is unchanged in rxe 0.9.5:
`reflex_enterprise/utils.py::get_backend_url()` builds the URL by assigning
`path + "?" + query` to `URL.pathname`, and the `pathname` setter percent-encodes `?`, so
the query string becomes part of the path and Starlette's `/abstract-wrapper-data` route
never matches.

Repro: start `demo_a1` (dev or prod), open `/model`, watch the network panel — or
`scripts/drive_aggrid.py <base> <shots> model` and read the `failed` array of
`shots/*/report.json`. The DB is populated (200 `friend` rows via `scripts/seed_db.py`)
and reachable; the request simply never reaches the route.
Identical on 0.9.10.post2 (`shots/dev_0910/report.json`) and reported in the previous
campaign, so pre-existing and version-independent.

### ISSUE 6 (LOW, downstream: reflex-enterprise, pre-existing) — rxe still calls the deprecated `console.*` helpers, so every enterprise app start prints a framework DeprecationWarning

`reflex_enterprise/app.py:154` (`console.info("Single port proxy mode enabled")`) fires on
every dev and prod start; `reflex_enterprise/utils.py:119` and `app.py:120` fire
`console.error` on the prod-tier gate and the logged-out gate — so the *error message a
user most needs to read* is preceded by a five-line DeprecationWarning about reflex
internals. Evidence: `logs/run_a1_dev.log:75`, `logs/run_a1_prod.log:68,2583`, and the
logged-out gate output quoted in "Setup". Present identically on 0.9.10.post2
(`logs/run_0910_dev.log:151,292`). 2026-08-27 FINDING-029, still open.

### ISSUE 7 (MEDIUM, downstream: reflex-enterprise, pre-existing) — `ag_grid.column_def()` silently discards unknown kwargs, which kills row selection in the shipped `ag_grid_finance` example

`ag_grid_finance` declares
`ag_grid.column_def(field="ticker", header_name="Ticker", filter=..., checkbox_selection=True)`.
rxe 0.9.5's `column_def(**kwargs)` drops any key its `ColumnDef` model does not know,
with no warning:

```bash
cd $A && CI=1 $A/venv_fin/bin/python -c "
from reflex_enterprise import ag_grid
print(ag_grid.column_def(field='ticker', header_name='Ticker', checkbox_selection=True).dict())
print(ag_grid.column_def(field='x', totally_bogus_kwarg=123).dict())"
# {'headerName': 'Ticker', 'field': 'ticker'}
# {'field': 'x'}
```

Result in the browser: no selection checkboxes, no selectable rows
(`ag-selection-checkbox` count 0, `.ag-row-selected` count 0 after a row click and after
Space), so `on_selection_changed` never fires and the recharts price chart — the point of
the example — never appears. No AG Grid warning either, because the prop never reaches
AG Grid. Repro: `scripts/drive_finance_sel.py http://localhost:5103 out`;
evidence `shots/fin_a1/finance_selection_report.json`,
`shots/fin_a1/finsel_01_rowclick.png`. Byte-identical on 0.9.10.post2
(`shots/fin_0910/finance_selection_report.json`), so not a regression: it is rxe's
`ColumnDef` model drifting from AG Grid 34 (which replaced `checkboxSelection` with
`rowSelection: {mode, checkboxes}`) plus a permissive `**kwargs` signature. Two fixes are
warranted downstream: reject/warn on unknown `column_def` kwargs, and update the example.

## Benign-but-surprising observations (recorded, not filed as issues)

- **AG Grid Enterprise trial banner** is printed as `console.error` (6–36 per enterprise
  route, counted separately as `console_license_noise` in the reports). Expected without a
  license key, on both versions.
- **`Unable to find the base Starlette app. Proxying will not be enabled.`**
  (`reflex_enterprise/proxy.py:135`) is printed on **every** run of the demo — dev and
  prod, both reflex versions — directly contradicting the `Single port proxy mode enabled`
  info line emitted moments earlier. The app works regardless. Downstream, pre-existing.
- **`Warning: Page <route> is being redefined with the same component.`** ×17 in the
  granian worker, **prod only**. Present identically on 0.9.10.post2
  (`logs/run_0910_prod.log`), so pre-existing; it looks like the prod worker re-registers
  the decorated pages after importing the app module.
- Deprecation warnings on both versions from the demo itself: `@rx.memo` without
  annotations (`formatters.py:208`), `rx.Model`, strings in `disable_plugins`
  (`reflex_enterprise/config.py:22`), implicit Radix Themes, `ArrayVar.foreach`
  (`reflex_enterprise/components/ag_grid/aggrid.py:1736`).
- `/editable` shows **2** sonner toasts in dev (the real one plus the ISSUE 2 error) and
  **1** in prod. The 2026-08-27 notes attributed the dev duplicate to a sonner rendering
  quirk; it is actually the ISSUE 2 error toast.
- `/state-grid` and `/model-ssrm` take ~35–39 s to drive, on both versions — that is my
  driver waiting on empty grids, not a perf cliff.
- `--prerelease=allow` also pulls **pydantic 2.14.0b2** into the 0.9.11a1 venvs (the
  stable baseline venv gets 2.13.5). That is uv's global prerelease flag, not a reflex pin.
- Frontend dependency deltas 0.9.10.post2 → 0.9.11a1 in this app
  (`artifacts/package_json.diff`): react-router 8.3.0 → 8.3.1, vite 8.2.0 → 8.2.2,
  sonner 2.0.7 → 2.0.8, `react-moment 1.2.2 → 2.0.2` + new `moment-duration-format 2.2.2`,
  `@radix-ui/react-form` 0.1.14 → 0.1.16, isbot 5.2.1 → 5.2.2, postcss-import 16 → 17.
  The react-moment bump is campaign FINDING-002; the demo's `rx.moment` usage
  (`row_counter`, `duration_from_now`) has no `on_change`, so it is unaffected and renders
  correctly.

## Layout of this artifact directory

```
NOTES.md                     this file
demo_a1/       demo_0910/    ag_grid demo copies (sources only; .web/venv/db excluded)
finance_a1/    finance_0910/ ag_grid_finance copies (offline-data patch applied)
scripts/                     drivers and probes (see "Setup" for how each is invoked)
  drive_aggrid.py            17-route sweep: screenshots, console, failed requests
  drive_deep.py              charts / fill handle / aligned grids / editable / selection
  drive_hydrate.py           hydrate-delta loss, first version
  drive_hydrate2.py          hydrate-delta loss, decisive version (ISSUE 2)
  drive_toasts.py            per-route sonner-toast census
  drive_aligned_hmr.py       aligned-grid wheel sync + hot-reload before/after
  probe_aligned.py           aligned-grid scrollLeft synchronisation probe
  drive_finance.py           ag_grid_finance sweep (fetch/paging/filter/sort/theme)
  drive_finance_sel.py       ag_grid_finance row-selection probe (ISSUE 7)
  probe_legacy_apis.py       FINDING-001/021/022/023 status, offline
  probe_masked_attrerror.py  FINDING-024 status, offline (ISSUE 3)
  seed_db.py                 insert N fake `friend` rows into the demo sqlite DB
logs/                        trimmed server logs (a note at the end of each says how many
                             noisy vite/bun lines were removed; nothing with an error,
                             warning or traceback was removed)
shots/dev_a1  dev_0910  prod_a1  prod_0910  fin_a1  fin_0910
                             screenshots + report.json / deep_report.json /
                             hydrate_report2.json / finance_report.json per configuration
artifacts/                   tracebacks, .web/package.json for both versions and their diff
```

## VERIFICATION: Shipped reflex-enterprise ag_grid demo cannot start: formatters.py bundles the stale pre-0.9.8 path "$/utils/components"

Independent adversarial verification (verifier agent, 2026-09-11). Reproduced from the
written repro alone in a fresh working dir with fresh PyPI-only venvs; the claimant's
app copies, venvs and running processes were not used.

- Working dir: `$SB/apps/verify2_ent_aggrid_0/`
- Venvs (mine, PyPI only): `$SB/envs/verify2_ent_aggrid_0` (reflex 0.9.11a1 + reflex-base 0.9.11a1
  + reflex-enterprise 0.9.5, Python 3.11) and `$SB/envs/verify2_ent_aggrid_0_b0910`
  (reflex 0.9.10.post2 + reflex-base 0.9.10.post2 + reflex-enterprise 0.9.5)
- Ports 5800-5803 / 10200-10203. All processes killed afterwards.
- Artifacts: `verification/issue1_bundle_path/`

### VERDICT: CONFIRMED as a real, reproducible defect — but it is a reflex-enterprise **demo** bug, not a reflex release issue, and three details of the claim are wrong.

| claim | verdict |
|---|---|
| Unpatched demo exits 1 at "Compile pages" on reflex 0.9.11a1 | **CONFIRMED**, byte-for-byte the stated error |
| Identical on reflex 0.9.10.post2, i.e. not a regression | **CONFIRMED** by my own baseline run |
| Downstream (reflex-enterprise) | **CONFIRMED**, and still unfixed on the rxe default branch |
| "stale **pre-0.9.8** path" | **WRONG** — stale since reflex **0.9.2** |
| fix needs `bundle_library()` **BOTH** at import time and in `formatter_page()` | **WRONG** — the page-eval call alone is sufficient |
| "**Shipped**" demo | **OVERSTATED** — demos are not in the published `reflex_enterprise` wheel |

### Reproduction (mine, from the written repro)

```bash
SB=/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad
W=$SB/apps/verify2_ent_aggrid_0
mkdir -p $W/logs && cp -r /home/user/reflex-enterprise/demos/ag_grid $W/shipped_a1
cd $W && uv venv $SB/envs/verify2_ent_aggrid_0 --python 3.11
UV_HTTP_TIMEOUT=180 uv pip install --python $SB/envs/verify2_ent_aggrid_0/bin/python \
    --prerelease=allow 'reflex==0.9.11a1' 'reflex-enterprise==0.9.5' \
    faker==36.2.2 pandas==2.2.3 aiosqlite greenlet          # cwd is $W, never /home/user/reflex
cd $W/shipped_a1
sed -i 's|^sqlalchemy.url = .*|sqlalchemy.url = sqlite:///reflex.db|' alembic.ini
CI=1 $SB/envs/verify2_ent_aggrid_0/bin/alembic upgrade head
CI=1 REFLEX_TELEMETRY_ENABLED=false $SB/envs/verify2_ent_aggrid_0/bin/reflex run \
    --frontend-port 5800 --backend-port 10200            # exit 1
```

Exit 1 during `Compile pages`, ending in

```
File ".../site-packages/reflex_enterprise/vars.py", line 166, in _validate_and_extend_return_expr
ValueError: Library $/app_components/ag_grid/formatters is not bundled. Use `from
reflex.components.dynamic import bundle_library; bundle_library('$/app_components/ag_grid/formatters')
to enable it it.
```

Baseline, same steps, `$SB/envs/verify2_ent_aggrid_0_b0910` (reflex 0.9.10.post2, **no**
`--prerelease=allow`), `$W/shipped_0910`, ports 5803/10203 → **identical exit 1 and identical
ValueError**. Not a regression of this release train.

Evidence: `verification/issue1_bundle_path/logs/shipped_a1_unpatched.trimmed.log`,
`.../shipped_0910_unpatched.trimmed.log`.

### Correction 1 — the path went stale at reflex 0.9.2, not 0.9.8

`bundle_library("$/utils/components")` names the *single shared memo module* that reflex
emitted up to and including 0.9.1. Greps of the published wheels
(`$W/histcheck/<ver>`, installed with `uv pip install --no-deps --target`):

| reflex | memo `Component.library` |
|---|---|
| 0.9.0, 0.9.1 | `$/utils/components` (bare — the demo's string), `reflex/compiler/utils.py:403,452` |
| 0.9.2 – 0.9.5 | `$/utils/components/<ExportName>` (per memo), `utils.py:474/426` |
| 0.9.6 – 0.9.11a1 | `$/app_components/<dotted module path>` mirrored, with the per-name path only as a fallback for `__main__`/unsafe names (`reflex_base/utils/memo_paths.py:library_for`) |

reflex-enterprise 0.9.5 declares `Requires-Dist: reflex[db]>=0.9.6`, so **the demo cannot
start on any reflex version rxe 0.9.5 permits** — it has been dead for the whole 0.9.6+ range,
across at least six reflex releases, not since 0.9.8.

Confirmed unfixed upstream: `reflex-dev/reflex-enterprise` default branch
`demos/ag_grid/ag_grid/formatters.py:16` (blob sha `fbd343d6`, commit `592d5cc1`) still reads
`dynamic.bundle_library("$/utils/components")`.

There is also a path-agnostic way to write the call that would never have gone stale —
`bundle_library()` accepts a Component and reads `.library`:
`probes/probe_memo_library.py` shows `row_counter(rowid="").library` is the live specifier and
`bundle_library(row_counter(rowid=""))` registers exactly it
(`verification/issue1_bundle_path/probes/probe_memo_library.out.txt`).

### Correction 2 — page-eval call alone is sufficient; import-time alone is not

Three variants of the demo, same venv, same everything else:

| variant | where `bundle_library("$/app_components/ag_grid/formatters")` is called | result |
|---|---|---|
| A | module import time only | **exit 1**, same ValueError (`logs/variantA_importtime_only_a1.trimmed.log`) |
| B | import time **and** inside `formatter_page()` | serves, `/formatters` HTTP 200 (`logs/variantB_import_plus_pageeval_a1.summary.txt`) |
| C | inside `formatter_page()` only | serves, `/formatters` HTTP 200 (`logs/variantC_pageeval_only_a1.summary.txt`) |

So the claim's "BOTH ... import-time only still fails" is half right: import-time only does fail,
but the import-time call contributes nothing to the compile. (It may still matter for the dev
granian worker, which never runs `compile_app()` — that is NOTES ISSUE 2's territory and was
not tested here.) Patched sources: `formatters_variant{A,B,C}_*.py`.

### The one reflex-side defect worth acting on (framework, pre-existing, not a regression)

`compile_app()` calls `reset_bundled_libraries()` **after** the app module has been imported —
`reflex/compiler/compiler.py:1212` in 0.9.11a1 (`:1209` in 0.9.10.post2) — so a user
`bundle_library()` at module scope is discarded before any page is evaluated. The remedy the
error message itself prints is therefore ineffective wherever a user would naturally put it,
and `bundle_library` is undocumented (no hit in `docs/`), so there is no written guidance to
fall back on. The only user-reachable place that survives is inside the page function.

Minimal repro, **pure reflex, no reflex-enterprise**
(`verification/issue1_bundle_path/minrepro_bundle_reset/`):

```bash
cd $W/minrepro_bundle_reset      # rxconfig.py + minapp/minapp.py, 40 lines
REFLEX_TELEMETRY_ENABLED=false $SB/envs/verify2_ent_aggrid_0/bin/reflex run \
    --frontend-port 5800 --backend-port 10200
# exit 1: RuntimeError: REPRO: '$/app_components/minapp/minapp' was bundled at import time
#         but is missing during page evaluation.
#         bundled_libraries=['react', '@emotion/react', '$/utils/context', '$/utils/state']
```

`bundle_reset_report_a1.json` / `bundle_reset_report_0910.json` record the list at both moments;
they are identical on 0.9.11a1 and 0.9.10.post2, so this too is pre-existing. `reset_bundled_libraries()`
has been inside `compile_app()` since reflex 0.9.2 (absent in 0.9.0) — the same release that moved the
memo path, which is why the two failures have always travelled together.

The rxe-side validation itself is **correct**, not over-eager: `reflex_base/components/dynamic.py`
`make_component` rewrites every `$/…` import in an eval'd renderer to
`window['__reflex'][<lib>]`, and `_compile_app` (`reflex/compiler/compiler.py:150`) populates
`window.__reflex` from `bundled_libraries` alone. An unbundled memo module would be `undefined`
at runtime, so refusing to compile is the right call — only the suggested fix is unusable.

### Refutations ruled out

- Environment/proxy/ports/cwd shadowing: the failure is offline and deterministic, happens during
  `Compile pages` before any network or bun install, from my own dirs with venv-absolute
  interpreters (`reflex.__file__` asserted under `$SB/envs/verify2_ent_aggrid_0`); ports were free.
- Flaky: 5/5 deterministic failures across two reflex versions and two app copies.
- Documented behaviour / API misuse by the tester: no — the demo source itself is what is stale.
- Pre-existing rather than new: **yes**, confirmed by my own 0.9.10.post2 baseline, and in fact
  pre-existing for the whole reflex 0.9.6+ range.

### Severity (my judgement)

- **reflex 0.9.11a1 release: not a blocker, not a regression.** Nothing in this train caused or
  worsened it.
- **reflex-enterprise: medium.** A repo demo that cannot start on any supported reflex is a bad
  first impression, and it is a one-line fix (`bundle_library(row_counter(rowid=""))` inside
  `formatter_page()`).
- **reflex: low-medium, separate ticket.** `bundle_library()` at import time being silently reset
  by `compile_app()` is a genuine framework usability defect with a 40-line pure-reflex repro; it
  is what makes the enterprise error message a dead end.

## VERIFICATION: Dev mode: one unserializable state var (rxe python-callable column defs) drops the ENTIRE hydrate delta on every page load — session state silently reverts and a raw internal ValueError is shown to the user

Independent adversarial verification (second agent, own working dir
`$SB/apps/verify2_ent_aggrid_1`, own baseline venv
`$SB/envs/verify2_ent_aggrid_1_b0910` = reflex 0.9.10.post2 + rxe 0.9.5, ports 5804-5807 /
10204-10207). Reproduced from the written repro only, then reduced to a 40-line app.
Artifacts: `verification/issue2_hydrate_delta/`.

### Verdict: CONFIRMED — genuine defect, but the report needs four corrections

**CONFIRMED (reproduced independently, then minimized):** a state var holding a plain python
callable that returns a Radix component makes every hydrate delta fail to encode; the whole
delta is dropped, and the session's server-side state is invisible to the UI until each var
changes again. No ag_grid, no `@rx.memo`, no `bundle_library` patch and none of the demo's
17 routes are needed — so this is *not* an artifact of the demo patch and not a demo bug.

Minimal repro (`verification/issue2_hydrate_delta/app/`, 40 lines):

```python
def cell_renderer(params: rx.Var) -> rx.Component:
    return rx.text("cell")            # any @radix-ui/themes component

class MinState(rx.State):
    count: int = 0
    col_defs: list[dict] = [{"field": "name", "cell_renderer": cell_renderer}]
```

```bash
V=$SB/apps/verify2_ent_aggrid_1
cd $V/minrx && CI=1 REFLEX_TELEMETRY_ENABLED=false $SB/envs/ent/bin/reflex run \
    --loglevel debug --frontend-port 5804 --backend-port 10204 > $V/logs/min_a1_dev.log 2>&1 &
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python $V/drive_min.py \
    http://localhost:5804 $V/shots min_a1_dev
```

Result on reflex 0.9.11a1 + rxe 0.9.5 (`reports/min_a1_dev_report.json`):
`initial "0"` → 3 clicks `"3"` → reload `"0"` → one more click `"4"`, plus
`"An error occurred. ValueError: Library @radix-ui/themes is not bundled…"` in the page body
(`shots/min_a1_dev_afterreload.png`), and one `[Reflex Backend Exception]` per page load with
exactly the reported stack (`logs/min_a1_dev.excerpt.txt`):
`reflex/state.py:2463 hydrate` → `emit_delta` → `reflex/app.py:1975 _sio_dumps` →
`reflex_base/utils/format.py:734 json_dumps` → `reflex_base/utils/serializers.py:176` →
`reflex_enterprise/vars.py:284 serialize_lambda` → `:244 create` → `:166 raise ValueError`.

**Not a regression — confirmed independently.** Same app, own venv with reflex 0.9.10.post2 +
rxe 0.9.5, ports 5805/10205: byte-identical outcome (`reports/min_0910_dev_report.json`
`"after_reload": "0"`, `"after_reload_plus_one_click": "4"`, 2 exceptions for 2 page loads,
`logs/min_0910_dev.excerpt.txt`). The claim's `regression: false` stands.

### Correction 1 (makes it WORSE) — this is not dev-only; a production configuration is affected

The real trigger is "the process serving the websocket never ran a real compile", not "dev".
Reflex itself spawns the **uvicorn/gunicorn production backend** as a separate process with
`__REFLEX_SKIP_COMPILE=true` (`reflex/utils/exec.py:783`), and any container that runs
`reflex export` in one step and serves the ASGI app in another does the same.

Demonstrated live against the *production build* of the minimal app, served by a separate
non-compiling backend process (`verification/issue2_hydrate_delta/serve_deploy_like.py`,
port 5807, `__REFLEX_SKIP_COMPILE=true` + `__REFLEX_MOUNT_FRONTEND_COMPILED_APP=true`,
`REFLEX_ENV_MODE=prod`):

```bash
cd $V/minrx && $SB/envs/ent/bin/python $V/serve_deploy_like.py 5807 > $V/logs/min_a1_deploylike.log 2>&1 &
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python $V/drive_min.py http://localhost:5807 $V/shots deploylike
```

`reports/deploylike_report.json`: reload → `"0"`, next click → `"4"`, 2 backend exceptions
(`logs/min_a1_deploylike.excerpt.txt`), and the end user sees
**"An error occurred. Contact the website administrator."** on every page load
(`shots/deploylike_afterreload.png`). `reflex run --env prod` is clean
(`reports/min_a1_prod_report.json`, 0 exceptions) only because `run_granian_backend_prod`
(`reflex/utils/exec.py:789`) serves in the very process that just compiled;
`should_use_granian()` (`exec.py:412`) picks uvicorn instead whenever uvicorn *and* gunicorn
are installed or `REFLEX_USE_GRANIAN=0`, and that path is broken in production.

### Correction 2 — "a single unserializable var takes down the entire delta" is not reflex behavior

Reflex tolerates unserializable state vars: `format.json_dumps` passes
`serializers.serialize` as the `default=` hook (`reflex_base/utils/format.py:730`), and that
returns `None` for a type with no serializer (`serializers.py:167`), so the value is encoded
as `null` and **the delta is still delivered**. Control app with no reflex-enterprise at all
(`verification/issue2_hydrate_delta/purerx/`, a state var holding an object with no
serializer, reflex 0.9.11a1 from `$SB/envs/smoke`, port 5806): 0 exceptions, state survives
the reload (`reports/purerx_report.json` → `"after_reload": "3"`).
The delta dies here only because rxe's registered serializer **raises**. That half of the
attribution belongs to reflex-enterprise, not to reflex.

### Correction 3 — the raw error text in dev is intended behavior, not part of the bug

`default_backend_exception_handler` (`reflex/app.py:133-165`) deliberately shows
`f"{type(exception).__name__}: {exception}"` when `not is_prod_mode()` and
"Contact the website administrator." otherwise. Showing the ValueError to the developer in
`reflex run` is the designed dev experience; the finding is the dropped delta, not the toast.

### Correction 4 — blast radius is narrower than stated, and it self-heals in dev

- `on_load` handlers still run and `is_hydrated` still becomes `true` during the failed
  hydrate (`reports/onload_a1_dev_onload.json`: `loaded = "on_load-ran"`,
  `is_hydrated = "hydrated"`), so only the hydrate delta itself is lost. That matters on
  reload/reconnect of an existing session, not on a first visit where the client already
  holds the defaults.
- In dev it cures itself after the **first** hot reload, as the report says: edit any app
  source file, and from then on 0 exceptions and the reload test returns `"3"`
  (`reports/pre_hmr_report.json` vs `reports/post_hmr_report.json`). Cause: the `.nocompile`
  marker (`reflex/utils/exec.py:494`) is deleted when it is read (`reflex/app.py:1591-1593`),
  so the reloaded worker performs a full compile. Dev impact window = server start → first
  source edit.
- **One-line workaround, verified:** `dynamic.bundle_library("@radix-ui/themes")` at app
  module import time → 0 exceptions, state survives the reload
  (`reports/workaround_report.json`, `logs/min_a1_dev_workaround.excerpt.txt`). It survives in
  a non-compiling worker precisely because that worker never calls
  `reset_bundled_libraries()`. (In the compiling process the same call is wiped — that is
  ISSUE 1's `compiler.py:1212` reset — but there the radix plugin bundles it anyway.)

### Mechanism, named at file:line (installed 0.9.11a1 wheel; identical on the release branch)

1. `reflex_components_radix/plugin.py:70` — `@radix-ui/themes` is registered **only** from
   `RadixThemesPlugin.enter_component`, i.e. inside the full compile walk.
2. `reflex/compiler/compiler.py:1174-1203` — when `app._should_compile()` is false,
   `compile_app()` re-evaluates pages and returns **before** the registry setup at
   `compiler.py:1212-1219` (`reset_bundled_libraries()` + `bundle_library(dep)` for every
   plugin frontend dependency). So a non-compiling worker keeps only
   `_default_bundled_libraries()`.
3. Proved offline with `verification/issue2_hydrate_delta/probe_registry.py` (run from the app
   dir): with `__REFLEX_SKIP_COMPILE=true` →
   `["react", "@emotion/react", "$/utils/context", "$/utils/state"]`; with a real compile →
   the same list **plus `@radix-ui/themes`**. The library *is* in the shipped frontend bundle
   either way, so the error is a false negative about the worker's own build.
4. `reflex_enterprise/vars.py:166` reads that compile-time, process-local registry at
   **websocket serialization time** and raises `ValueError` from inside `json.dumps`, which
   aborts encoding of the whole packet (`socketio/packet.py:64` → `reflex/app.py:1975`).

### Attribution and severity (my judgement)

Root cause is reflex-enterprise: `serialize_lambda` performs compile-time validation during
runtime serialization and raises inside a JSON `default=` hook. Fixing either half is enough
— rxe skipping/soft-failing the bundle check when no compile context exists, or reflex making
the registry reflect the actual build in non-compiling processes (populate plugin frontend
dependencies on the backend-only paths of `compile_app`, or persist the bundled set into
`.web` next to the stateful-pages marker and load it there).

Severity **medium** for this release train (claim said high): not a regression, root cause
downstream, one-line workaround, and the default `reflex run --env prod` path is clean.
It is *not* release-blocking for reflex 0.9.11a1. For reflex-enterprise it is the most
user-visible open bug in this cluster, and correction 1 (silent state loss plus an error
banner for end users on the uvicorn prod backend) makes it worth fixing on both sides rather
than only in dev-mode terms. No matching issue found in reflex-dev/reflex.

Processes started for this verification (all killed): dev servers on 5804/10204 (0.9.11a1)
and 5805/10205 (0.9.10.post2), pure-reflex control on 5806/10206, prod + deploy-like backend
on 5807.
