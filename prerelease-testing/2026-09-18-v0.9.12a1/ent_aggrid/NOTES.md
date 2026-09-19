# ent_aggrid — reflex-enterprise 0.9.5 ag_grid demos on reflex 0.9.12a1 vs 0.9.11.post1

Cluster: `ent_aggrid`. Tested 2026-09-19.
Every package came from PyPI (plus the published reflex-enterprise 0.9.5 wheel) into
isolated uv venvs. Nothing was ever installed from, or run inside, `/home/user/reflex`.

| stack | reflex | reflex-base | reflex-enterprise | radix | core | code | recharts |
|---|---|---|---|---|---|---|---|
| **under test** | 0.9.12a1 | 0.9.12a1 | 0.9.5 (wheel) | 0.9.10a1 | 0.9.10a1 | 0.9.6a1 | 0.9.4a1 |
| **baseline**   | 0.9.11.post1 | 0.9.11.post1 | 0.9.5 (wheel) | 0.9.9 | 0.9.9 | 0.9.5 | 0.9.3 |

Full resolved lists: `artifacts/freeze_venv_new.txt`, `artifacts/freeze_venv_prev.txt`.

## Headline results

1. **No regression anywhere.** All 17 ag_grid demo routes behave identically on
   0.9.12a1 (dev and prod) to the last known-good enterprise run, and `ag_grid_finance`
   is byte-identical on 0.9.12a1 and 0.9.11.post1. `shots/prod_new/report.json` diffs to
   **zero** against the previous campaign's `prod_a1` report (reflex 0.9.11a1).
2. **0.9.12a1 FIXES a total dev-mode outage that 0.9.11.post1 has.** On
   reflex 0.9.11.post1 + rxe 0.9.5 the granian worker **dies at startup** while
   serializing the initial state (`ValueError: Library @radix-ui/themes is not bundled`
   raised by rxe's `LiteralLambdaVar`), so the whole backend is dead and the demo is
   unusable: every route shows 0 rows and the UI toasts
   *"Cannot connect to server: websocket error."* On 0.9.12a1 the worker starts cleanly,
   **0** backend exceptions in a full 17-route sweep, and every route renders data.
   See "Finding A" below.
3. **Router split (#7068) works end-to-end in the enterprise demo.** The demo's header
   `Select` binds `value=State.router.page.path`; it compiles to
   `reflex___state____state.rx_router_page_rx_state_?.["path"]` and stays correct across
   direct load, Select-driven redirect, client-side link nav, and browser back/forward.
   Navigation delta measured on the wire: **527 bytes** (only `rx_router_page`,
   `rx_router_url`, `rx_router_route_id`, `is_hydrated`) versus a **20 162 byte** first
   event — the PR's "connection-static router data ships once" claim holds in a real app.
4. **Auto-memo transparency (#6850) is live and harmless for ag-grid.** Every compiled
   ag-grid/radix wrapper is now `memo(({children, ...rest}) => ... mergeSlotProps(rest, {...}))`
   and `mergician@v2.0.2` is in `.web/package.json`. No render, ref, `gridApi` or
   event-handler breakage was observed on any of the 17 routes in dev or prod.
5. The four pre-existing rxe 0.9.5 demo defects are unchanged (stale bundle path,
   `ModelWrapper` URL `%3F`, ag-grid 34.3.1 vs ag-charts 11.2.4, `column_def()` dropping
   unknown kwargs). Not new, not this release's fault — listed at the end for completeness.

## Setup / exact rerun commands

```bash
SB=/tmp/claude-0/.../scratchpad          # any scratch root
A=$SB/apps/ent_aggrid
mkdir -p $A/{logs,shots,scripts,artifacts}

# --- venvs (NEVER run uv from /home/user/reflex: its [tool.uv] exclude-newer
#     silently filters out the fresh alphas) ---
cd $SB
uv venv $A/venv_new --python 3.11
UV_HTTP_TIMEOUT=300 uv pip install --python $A/venv_new/bin/python --prerelease=allow \
    'reflex==0.9.12a1' 'reflex-components-core==0.9.10a1' 'reflex-components-radix==0.9.10a1' \
    'reflex-components-code==0.9.6a1' 'reflex-components-dataeditor==0.9.3a1' \
    'reflex-components-gridjs==0.9.2a1' 'reflex-components-markdown==0.9.4a1' \
    'reflex-components-plotly==0.9.7a1' 'reflex-components-recharts==0.9.4a1' \
    'reflex-components-sonner==0.9.4a1' \
    "reflex-enterprise[mcp] @ file://$SB/wheels/reflex_enterprise-0.9.5-py3-none-any.whl" \
    'faker==36.2.2' 'pandas==2.2.3' aiosqlite greenlet 'yfinance==0.2.54'

uv venv $A/venv_prev --python 3.11
UV_HTTP_TIMEOUT=300 uv pip install --python $A/venv_prev/bin/python \
    'reflex==0.9.11.post1' \
    "reflex-enterprise[mcp] @ file://$SB/wheels/reflex_enterprise-0.9.5-py3-none-any.whl" \
    'faker==36.2.2' 'pandas==2.2.3' aiosqlite greenlet 'yfinance==0.2.54'
# NOTE: pass --prerelease=allow AND name the component alphas explicitly for venv_new,
# otherwise reflex 0.9.12a1 installs against STABLE component packages.

# --- apps (already patched copies live next to this NOTES.md) ---
cp -r <this dir>/demo_new    $A/demo_new
cp -r <this dir>/finance_new $A/finance_new
cp -r <this dir>/scripts/*.py $A/scripts/

# --- db for the ag_grid demo (it ships an empty DB and a placeholder alembic URL) ---
cd $A/demo_new && CI=1 $A/venv_new/bin/alembic upgrade head
CI=1 $A/venv_new/bin/python $A/scripts/seed_db.py 200

# --- dev run (0.9.12a1) ---
cd $A/demo_new && CI=1 REFLEX_TELEMETRY_ENABLED=false $A/venv_new/bin/reflex run \
    --loglevel debug --frontend-port 3580 --backend-port 8580 > $A/logs/run_new_dev.log 2>&1 &

cd $A   # NEVER /home/user/reflex
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $SB/envs/driver/bin/python $A/scripts/drive_aggrid.py      http://localhost:3580 $A/shots/dev_new
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $SB/envs/driver/bin/python $A/scripts/drive_deep.py        http://localhost:3580 $A/shots/dev_new
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $SB/envs/driver/bin/python $A/scripts/drive_hydrate2.py    http://localhost:3580 $A/shots/dev_new
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $SB/envs/driver/bin/python $A/scripts/drive_router_nav.py  http://localhost:3580 $A/shots/dev_new
NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
  $SB/envs/driver/bin/python $A/scripts/dump_serialization.py http://localhost:3580 $A/shots/ser_new

# --- prod run (ONE port for both flags; CI=1 does NOT bypass the prod tier gate,
#     APP_HARNESS_FLAG=1 does -- reflex_enterprise/utils.py::is_in_app_harness()) ---
cd $A/demo_new && CI=1 APP_HARNESS_FLAG=1 REFLEX_TELEMETRY_ENABLED=false \
    $A/venv_new/bin/reflex run --env prod --loglevel debug \
    --frontend-port 3582 --backend-port 3582 > $A/logs/run_new_prod.log 2>&1 &
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python $A/scripts/drive_aggrid.py \
    http://localhost:3582 $A/shots/prod_new

# --- baseline (0.9.11.post1): identical steps with venv_prev / demo_prev on 3581/8581 ---

# --- ag_grid_finance ---
cd $A/finance_new && CI=1 REFLEX_TELEMETRY_ENABLED=false $A/venv_new/bin/reflex run \
    --loglevel debug --frontend-port 3584 --backend-port 8584 > $A/logs/run_fin_new_dev.log 2>&1 &
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python $A/scripts/drive_finance.py     http://localhost:3584 $A/shots/fin_new
NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python $A/scripts/drive_finance_sel.py http://localhost:3584 $A/shots/fin_new

# --- offline probes (seconds, no server) ---
cd $A && $A/venv_new/bin/python $A/scripts/probe_legacy_apis.py
cd $A && $A/venv_new/bin/python $A/scripts/probe_masked_attrerror.py
```

## Patches carried in the app copies (NOT findings of this release)

Both patches were written by the 2026-09-10 campaign and are reused verbatim so the
A/B compares byte-identical app code.

- `demo_new/ag_grid/formatters.py` — the shipped demo calls
  `dynamic.bundle_library("$/utils/components")`, a pre-0.9.8 path. Since 0.9.8 an
  `@rx.memo` component compiles under `$/app_components/<module path>`, and
  `compile_app()` calls `reset_bundled_libraries()` *after* importing the app module,
  so the call must run at **page eval time**, not only at import time. The patch adds
  `_bundle_renderer_libraries()` bundling `$/app_components/ag_grid/formatters` and calls
  it from both places. Without it the demo cannot start on any current reflex.
- `demo_new/alembic.ini` — `sqlalchemy.url` placeholder replaced with `sqlite:///reflex.db`.
- `finance_new/ag_grid_finance/ag_grid_finance.py` — this environment's egress proxy 403s
  `fc.yahoo.com`, so `yf.download()` returns an empty frame. `_offline_download()`
  substitutes a deterministic frame with exactly yfinance's shape (MultiIndex
  `(ticker, field)` columns, `DatetimeIndex` named `Date`). `import yfinance` is kept.
  All finance prices below are therefore synthetic; the grid/pagination/filter/sort/
  theme/state code paths are the real ones.
- Harness only: `CI=1` bypasses `AppEnterprise._check_login()`;
  `APP_HARNESS_FLAG=1` additionally bypasses the prod tier gate;
  `scripts/seed_db.py` inserts 200 fake `friend` rows.

## Results

N = reflex 0.9.12a1 + rxe 0.9.5; B = reflex 0.9.11.post1 + rxe 0.9.5.
`n/a` = could not be run on that stack (see Finding A).

| # | Check | dev N | dev B | prod N | note |
|---|---|---|---|---|---|
| 1 | app compiles + backend worker survives startup | PASS | **FAIL** | PASS | Finding A |
| 2 | `/` index, 17 demo cards + links | PASS | n/a | PASS | prod shows 18 links vs dev 17 (pre-existing dev/prod delta) |
| 3 | `/formatters` python-callable renderers + formatters (3 tab styles) | PASS | n/a | PASS | flag/currency/percent/reverse all render |
| 4 | `/formatters` `@rx.memo` row-counter button | PASS | **FAIL** | PASS | N: 0→1→2; B: stuck at `0 (∞)` |
| 5 | `/formatters` `@rxe.static` "Raw Data" dialog | PASS | n/a | PASS | |
| 6 | `/editable` cell edit → `on_cell_value_changed` → toast | PASS | n/a | PASS | N emits **1** toast; 0.9.11a1 emitted 2 (2nd was the bundling error) |
| 7 | `/master-detail` expand → detail row | PASS | n/a | PASS | |
| 8 | `/tree` group expand | PASS | n/a | PASS | |
| 9 | `/pivot` pivot columns + sidebar tool panel | PASS | n/a | PASS | |
| 10 | `/selected-items` Select All / Deselect All | PASS | **FAIL** | PASS | N: 0→128→0; B: stays 0 |
| 11 | `/cell-selection` range select echoed to state | PASS | **FAIL** | PASS | |
| 12 | `/fill-handle` drag fill | PASS | n/a | n/t | |
| 13 | `/aligned-grids` two grids render + sort | PASS | **FAIL** | PASS | B: 0 rows |
| 14 | `/state-grid` "Load columns"/"Load data" | PASS | **FAIL** | PASS | N: 0→26 rows; B: stays 0 |
| 15 | `/simple-serialization` + `/advanced-serialization` round-trip | PASS | **FAIL** | PASS | |
| 16 | `/integrated-charts` grid + range + context menu | PASS | n/a | PASS | chart still does not draw — pre-existing Issue D |
| 17 | `/model`, `/model-auth`, `/model-ssrm` datasource | FAIL | FAIL | FAIL | pre-existing Issue C (`%3F` in URL, 404) |
| 18 | generic sort / floating filter on every route | PASS | n/a | PASS | |
| 19 | hydrate delta reaches the client (session survives reload) | **PASS** | n/a | PASS | was FAIL on 0.9.11a1/0.9.10.post2 — now fixed |
| 20 | router split: direct load / Select nav / link nav / back / forward | PASS | n/t | n/t | `shots/dev_new/router_nav_report.json` |
| 21 | router navigation delta size | 527 B | n/t | n/t | vs 20 162 B first event |
| 22 | compat shims (`dynamic.bundled_libraries`, `page.DECORATED_PAGES`, `rxe.vars.get_bundled_libraries`, `LiteralLambdaVar.create`) | PASS | n/t | — | `scripts/probe_legacy_apis.py` |
| 23 | finance: initial render + "Fetch Latest Data" (650 rows) | PASS | PASS | n/t | identical on both |
| 24 | finance: pagination 20/50 + next page | PASS | PASS | n/t | identical |
| 25 | finance: ticker filter + Close sort | PASS | PASS | n/t | identical |
| 26 | finance: theme switch quartz/balham/alpine/material | PASS | PASS | n/t | identical |
| 27 | finance: row selection → recharts chart | FAIL | FAIL | n/t | pre-existing Issue E |
| 28 | `AttributeError` inside a cached var is diagnosable | FAIL | FAIL | — | pre-existing Issue F |

`n/t` = not tested in that configuration.

## Finding A (HIGH, *fixed* in 0.9.12a1 — regression on the PREVIOUS stable)

**reflex 0.9.11.post1 + reflex-enterprise 0.9.5: the granian dev worker dies at
startup and the ag_grid demo has no backend at all.**

Every `reflex run` (dev) of the demo on 0.9.11.post1 crashes worker-1 while
`compile_app()` builds the initial state:

```
Process granian-worker:
  reflex/app.py:766 __call__ -> app.py:1682 _compile
  reflex/compiler/compiler.py:1234 compile_app -> utils._compile_initial_state
  reflex/compiler/utils.py:269 -> reflex_base/utils/format.py:734 json_dumps
  -> compiler/utils.py:266 serialize_initial_value
  -> reflex_enterprise/vars.py:284 serialize_lambda
  -> reflex_enterprise/vars.py:244 LiteralLambdaVar.create
  -> reflex_enterprise/vars.py:166 _validate_and_extend_return_expr
ValueError: Library @radix-ui/themes is not bundled.
[ERROR] Unexpected exit from worker-1
```

`reflex run` then prints "App running at / Backend running at" anyway, so the failure is
easy to miss; the frontend serves fine but nothing is listening on the backend port.
The browser shows the Sonner toast
*"Cannot connect to server: websocket error. Check if server is reachable at
ws://localhost:8581/_event"* and every grid renders zero rows.

Reproduced **twice** (first run and a clean restart): `logs/run_prev_dev.log` and
`logs/run_prev_dev2.log`, traceback isolated in
`artifacts/prev_0911post1_worker_crash.txt`, dead-backend sweep in
`shots/dev_prev/report.json` (rows=0 on 10 of 17 routes; `/editable`'s toast text is the
websocket error).

On **0.9.12a1** the same app, same venv layout, same patches: worker starts, the full
17-route sweep logs **0** `Reflex Backend Exception` blocks and **0** worker exits
(`logs/run_new_dev.log`), and the `@rx.memo` row counter survives a reload
(`shots/dev_new/hydrate_report2.json`: `after_3_clicks=3 → after_reload=3 →
after_reload_plus_one_click=4`; on 0.9.11a1 this read `3 → 0 (∞) → 4`).

This is the single most valuable result of the cluster: **0.9.12a1 should ship**, because
the currently published stable cannot run the flagship enterprise ag-grid demo in dev.
Whatever in this train repopulates `bundled_libraries` before `_compile_initial_state`
(RegistrationContext / `Tag` render / auto-memo work) also cures the long-standing
"whole hydrate delta dropped" bug filed in the two previous campaigns.

*Caveat for the release lead:* because 0.9.11.post1's backend is dead in dev, the
route-by-route dev A/B against the previous stable is not meaningful. The dev-mode
"no regression" claim above therefore rests on the comparison with the previous
campaign's **reflex 0.9.11a1** dev sweep (identical except the two ISSUE-2 artifacts),
and on the prod A/B, which **is** valid: `shots/prod_new/report.json` diffs to zero
against `.../2026-09-10-v0.9.11a1/ent_aggrid/shots/prod_a1/report.json`.

## Router split verification (#7068) — `shots/dev_new/router_nav_report.json`

| step | result |
|---|---|
| direct load `/tree` | header Select reads `Tree (enterprise)` |
| Select → Pivot | URL `/pivot`, Select reads `Pivot` |
| client-side link → `/formatters` | URL `/formatters`, Select reads `AG Grid Formatters` |
| `@rx.memo` counter after client-side nav | renders `0 (∞)`, click → `1 (00:01)` |
| browser Back | `/`, Select empty (correct: demo maps `/` to `""`) |
| browser Forward | `/formatters`, Select restored |
| nav delta on the wire | 527 B: `rx_router_page`, `rx_router_url`, `rx_router_route_id`, `is_hydrated` only |
| first event on a connection | 20 162 B (headers + session + page + url + route_id + app state) |

`State.router.page.path` compiles to
`reflex___state____state.rx_router_page_rx_state_?.["path"]` — the per-field base var,
exactly as #7068 describes. rxe itself only ever reads the public switchboard
(`self.router.session.*`, `self.router.url`, `self.router.headers.cookie`,
`event.router_data`) so nothing in the enterprise package needed to change.

## Auto-memo transparency (#6850) in ag-grid — static + runtime evidence

- `.web/package.json` gains `"mergician": "v2.0.2"` (`artifacts/package_demo_new.json`;
  diff vs the 0.9.11a1 build is in `artifacts/package_json.diff` plus react-router
  8.3.1 → 8.4.0).
- Every tagged-root wrapper in `.web/app_components/ag_grid/*.jsx` is now
  `memo(({children, ...rest}) => ... jsx(X, {...mergeSlotProps(rest, ({...}))}, children))`;
  untagged roots (`Foreach`, `Cond`) keep the bare `({children})` signature, as the PR says.
- Runtime: 17 routes × (dev, prod) with grids, cell renderers, `gridApi` calls,
  `on_cell_value_changed`, selection events, master/detail, pivot sidebars — **0**
  page errors and **0** non-license console errors. The ag-grid `api` object is reached
  through rxe's own ref plumbing and was unaffected.

## Benign-but-surprising observations

1. **Prod index has 18 links, dev has 17.** `shots/prod_new/report.json` vs
   `shots/dev_new/report.json`. Identical in the previous campaign's prod run, so it is a
   pre-existing dev/prod difference (an extra react-router-emitted link), not new.
2. **`/advanced-serialization` body text is 1648 chars on 0.9.12a1 and 1853 on 0.9.11a1.**
   The 205-char delta is exactly the removed error panel
   *"An error occurred. ValueError: Library @radix-ui/themes is not bundled … enable it it."*
   — i.e. a consequence of the fix, not lost content. Dumps in
   `artifacts/advanced-serialization_{before,after}.txt`.
3. **rxe prints framework `DeprecationWarning`s on every start** (`console.info`,
   `console.error`, `ArrayVar.foreach`, `@rx.memo` without annotations, `reflex.Model`).
   Unchanged from 0.9.11.post1; noisy but harmless. `logs/run_new_dev.log`.
4. `reflex_enterprise/proxy.py:135` logs *"Unable to find the base Starlette app.
   Proxying will not be enabled."* on every start even though `use_single_port=True`.
   Present on both versions.
5. `/model-ssrm` and `/state-grid` take 34–39 s in the driver on **both** versions because
   the driver waits out timeouts on grids that never fill; not a perf change.

## Pre-existing reflex-enterprise 0.9.5 defects re-confirmed (NOT this release)

Each was checked on both 0.9.12a1 and (where the baseline could run) 0.9.11.post1, and
each was already filed by the 2026-08-27 and 2026-09-10 campaigns.

- **Issue B — shipped demo cannot start.** `demos/ag_grid/ag_grid/formatters.py:16`
  bundles the stale `$/utils/components`. Unpatched, `reflex run` exits with
  `ValueError: Library $/app_components/ag_grid/formatters is not bundled.` on every
  current reflex. See "Patches" above; traceback in
  `artifacts/traceback_shipped_demo_a1_bundle_path.txt`.
- **Issue C — `ModelWrapper` datasource URL percent-encodes `?`.** Every row fetch goes to
  `…/abstract-wrapper-data%3FstartRow=0&…` and 404s, so `/model`, `/model-auth` and
  `/model-ssrm` never load a row (the DB has 200 rows and is reachable).
  `reflex_enterprise/utils.py::get_backend_url()` assigns `path + "?" + query` to
  `URL.pathname`, whose setter escapes `?`. Evidence: the `failed` arrays of
  `shots/dev_new/report.json` and `shots/prod_new/report.json`.
- **Issue D — ag-grid 34.3.1 pinned against ag-charts 11.2.4.** `/integrated-charts`
  logs *"AG Grid version 34.3.1 and AG Charts version 11.2.4 is not supported"*, choosing
  a chart raises `Cannot assign to read only property 'api'`, `chart_wrappers = 0`.
  `shots/dev_new/deep_report.json`, `shots/dev_new/integrated_charts_view.png`.
- **Issue E — `ag_grid.column_def()` silently drops unknown kwargs**, so
  `checkbox_selection=True` in `ag_grid_finance` never reaches AG Grid: 0 selection
  checkboxes, 0 selected rows after click and after Space, `on_selection_changed` never
  fires, the recharts price chart never appears. Identical on both versions
  (`shots/fin_new/finance_selection_report.json` == `shots/fin_prev/...`). Repro:
  `$A/venv_new/bin/python -c "from reflex_enterprise import ag_grid;
  print(ag_grid.column_def(field='x', totally_bogus_kwarg=123).dict())"` → `{'field': 'x'}`.
- **Issue F — `AttributeError` inside a `CachedVarOperation` is masked** as
  `VarAttributeError: Attribute _cached_get_all_var_data not found.` with no `__cause__`.
  `scripts/probe_masked_attrerror.py`, same on both versions. This is the mechanism that
  made the 0.9.9a1 enterprise breakage undebuggable; worth fixing independently.

## What is in this directory

```
demo_new/      patched copy of /home/user/reflex-enterprise/demos/ag_grid (17 routes)
finance_new/   patched copy of reflex-examples/ag_grid_finance (offline data generator)
scripts/       Playwright drivers + offline probes (run with the driver venv's python)
  drive_aggrid.py         17-route sweep, per-route interactions, report.json
  drive_deep.py           charts / fill handle / aligned / editable / selection detail
  drive_hydrate2.py       hydrate-delta repro (counter value survives a reload?)
  drive_router_nav.py     NEW: router-split probe via the demo's own nav Select + ws frames
  dump_serialization.py   NEW: body-text dump of the two serialization routes
  drive_finance.py / drive_finance_sel.py    ag_grid_finance
  probe_legacy_apis.py    compat-shim status, no server
  probe_masked_attrerror.py  Issue F, no server
  seed_db.py              200 fake friend rows
shots/         report.json per configuration + a handful of PNGs
logs/          server logs (dev/prod, both versions; trimmed to 400 KB)
artifacts/     tracebacks, package.json diffs, venv freezes, serialization text dumps
```

## Appendix: shipped (unpatched) demo on 0.9.12a1

Confirmed that Issue B still blocks the demo as shipped, on the new release too:

```bash
cp -r /home/user/reflex-enterprise/demos/ag_grid $A/demo_shipped
sed -i 's|^sqlalchemy.url = .*|sqlalchemy.url = sqlite:///reflex.db|' $A/demo_shipped/alembic.ini
cd $A/demo_shipped && CI=1 $A/venv_new/bin/alembic upgrade head
cd $A/demo_shipped && CI=1 REFLEX_TELEMETRY_ENABLED=false $A/venv_new/bin/reflex export --frontend-only --no-zip
# exit 1
# ValueError: Library $/app_components/ag_grid/formatters is not bundled.
```

Full log: `artifacts/shipped_unpatched_demo_0912a1_export_fail.log`.
Fix belongs in the reflex-enterprise demo, not in reflex.
