# Experimental Community grid review

This draft adds `reflex_components_internal.community_grid`, using **AG Grid Community 34.3.1**, without importing `reflex-enterprise` or installing Enterprise packages. The React renderer is shared by the Python adapter, this review harness, and `compact.html` for dashboard widgets. The dependable existing enterprise wrapper is untouched. An original table clone was deliberately deferred; this is a bounded adapter, not an AG Grid replacement.

## Provenance and dependency boundary

- Reflex/shared components: `reflex-dev/reflex` at `17370c28`, actual `packages/reflex-components-internal/src/reflex_components_internal`.
- Shared theme tokens: actual consuming app `flexgen/assets/css/globals.css` (`--font-sans`, `--secondary-*`, `--primary-9`, `--radius-ui-md`). The renderer maps these with neutral fallbacks, rather than inventing another palette. Color variables update light/dark surfaces, including AG filters and pagination.
- Existing `reflex-dev/reflex-enterprise` source audited at `f7d36b1fae806119981c80bba01e4e72c7347d74`. Its `AgGrid.lib_dependencies` installs Enterprise/chart Enterprise packages, so this adapter is independent; no implementation was copied.
- npm metadata and `evidence/runtime-dependencies.json` show `ag-grid-community@34.3.1` and `ag-grid-react@34.3.1` (MIT), with Community's `ag-charts-types@12.3.1` and React adapter's `prop-types`. `AllCommunityModule` is supplied per grid. No license keys, Enterprise modules, grouping, pivoting, Set Filter, advanced filters, master/detail or server-side row model.
- Version-specific API truth comes from the installed 34.3.1 package declarations. Current online docs may describe newer versions: [AG Grid state](https://www.ag-grid.com/react-data-grid/grid-state/), [Community installation](https://www.ag-grid.com/react-data-grid/installation/), [theming](https://www.ag-grid.com/react-data-grid/theming/).

## Small Python API

```python
import reflex_components_internal as ui

ui.community_grid(
    row_data=[{"id": "account-1", "name": "Account A", "revenue": 123}],
    column_defs=[
        {"field": "name", "headerName": "Account", "floatingFilter": True},
        {"field": "revenue", "filter": "agNumberColumnFilter"},
    ],
    row_id_key="id",
    selection_mode="multiRow",  # none (default), singleRow, multiRow
    page_size=25,
    height="420px",
)
```

Each row requires a stable, unique string/finite-number key. Missing/duplicate keys throw actionable validation errors instead of silently collapsing rows. Number/string forms collide intentionally (`1` and `"1"`). Reversing the input data preserves row selection by ID.

Columns accept `field`, `colId`, `headerName`, `width`, `minWidth`, `maxWidth`, `flex`, `hide`, `pinned`, `sort`, `sortIndex`, `sortable`, `resizable`, `filter`, `floatingFilter`, `cellDataType`, `wrapText`, `autoHeight`. Unknown options are rejected explicitly. Filters are `false`, `agTextColumnFilter` (default), `agNumberColumnFilter`, `agDateColumnFilter`; no arbitrary callbacks/components or Enterprise filters. Numeric columns should author a number filter. Data is read-only; no cell mutation or automatic business write.

Other props: `pagination=True`, `quick_filter=""`, `loading=False`, `initial_state={...}`, `on_state_changed(state)`, `on_selection_changed(ids)`, and ordinary Reflex size/class properties. `initial_state` is consumed on mount; remount with saved state to restore. The adapter does not store preferences or write to a business database. The harness Save/Restore buttons keep state only in memory. App owners decide persistence and should debounce server event handlers if desired. Fixed/resized widths restore; flex columns adapt to available width. Pin commands convert a column to fixed width so its width survives restoration.

## Feature/evidence matrix

| Feature | Implemented surface | Browser proof |
|---|---|---|
| Sort | Header click, normal AG keyboard behavior | Ascending state, descending numeric order |
| Basic/quick filter | Floating filters; external quick-filter string | Region filter counts and cross-cell token search |
| Resize | Header boundary drag | 210→260px and fixed-width restoration |
| Pin/hide/order | Nonmodal Columns menu, native keyboard-operable controls | Pin left, hide Active, move Revenue earlier |
| Select | AG checkbox/click selection, stable IDs | Selection callback and input-row reversal continuity |
| Pagination | AG footer, configurable page size/disable | Next page and saved pagination |
| Keyboard | AG focus/navigation | ArrowDown increments actual focused row index |
| Saved view | `initial_state` + state callback | Sort/filter/order/pin/hide/fixed-size/selection/pagination after remount |
| Virtualization | AG native bounded viewport | 10k **unpaginated** rows, DOM bounds before/after scroll to Account9999 |
| Responsive/theme/states | Shared CSS variables, bounded panel | 1440/1024/390px normal/menu/dark/empty/loading captures |

Screenshots and raw test results are in `evidence/`. The unpaginated viewport observation verifies bounded DOM rendering; it is **not a throughput or latency benchmark**. The default paginated fixture also uses 10k rows; pagination alone is not proof of virtualization.

## Reproduce

In this cloud environment:

```bash
cd /workspace/grid-work/experiments/community-grid
npm --cache /tmp/grid-npm-cache ci --ignore-scripts
# Shared renderer is outside the harness directory; resolve its npm imports.
ln -s experiments/community-grid/node_modules ../../node_modules  # only if absent
npm test
npm run build
npx playwright test  # uses /usr/bin/chromium; override CHROMIUM_PATH if needed
npm run dev -- --port 4191
```

`compact.html` uses the exact renderer with 100 deterministic rows and no outer harness controls. Copy the full `dist/` directory to any static preview subdirectory; its assets use relative paths. No production hosting/deployment is configured.

Python verification (from the isolated worktree):

```bash
cd /workspace/grid-work
VIRTUAL_ENV=/workspace/reflex/.venv UV_CACHE_DIR=/tmp/grid-uv-cache \
PYTHONPATH=/workspace/grid-work/packages/reflex-components-internal/src \
uv run --active --no-sync pytest tests/units/reflex_components_internal/components/base/test_community_grid.py -q
```

The synthetic `reflex_app/` fixture also compiled through the actual Python adapter (`evidence/reflex-compile.log`). Run from that directory with the same environment plus `REFLEX_DIR=/tmp/grid-reflex-dir` and `npm_config_cache=/tmp/grid-npm-cache`, then `uv run --active --no-sync reflex compile --no-rich`.

`uv run python scripts/make_pyi.py` completed successfully. Its current `DEFAULT_TARGETS` excludes `reflex-components-internal`, so it generated no new internal hash entries; an explicit internal path is also filtered out. No unrelated registry edits were invented. Package publishing/type-stub review remains necessary before promoting this experimental API.

## Remaining review scope

No in-cell editing, CSV/export UI, custom renderers, per-column settings editors, accessible error recovery boundary, local-storage persistence, full screen-reader audit or performance benchmark. Selection callbacks send IDs, not whole records. This draft's Columns menu uses native controls with shared tokens; a future promotion should use the Python shared UI controls/complete interaction design. Auto-height/wrapped columns are configurable but have not been benchmarked. Client-side data requires memory proportional to supplied records. The production build warns about a ~1.21MB minified shared bundle (~344KB gzip); lazy load grids rather than adding this to every route.

## Executed checks

- Shared internal package unit suite: **19 passed** (including adapter's 3 tests).
- Boundary model tests: **2 passed**.
- Chromium suite: **5 passed**, including unpaginated 10k scrolling (22 DOM rows at both ends, 360000px content height) and responsive/state interactions.
- Real Reflex compile: succeeded. Real frontend/backend smoke (`node runtime-smoke.mjs` while the fixture runs): Python received selected ID `a` and descending Revenue state, with row-index 0 displaying `456`; no browser page errors.
- Scoped Ruff lint/format and scoped Pyright: clean. No full framework test or full project type-check claim.

For the real runtime smoke, run this in `reflex_app/` with the Python environment above:

```bash
REFLEX_DIR=/tmp/grid-reflex-dir npm_config_cache=/tmp/grid-npm-cache \
VIRTUAL_ENV=/workspace/reflex/.venv UV_CACHE_DIR=/tmp/grid-uv-cache \
PYTHONPATH=/workspace/grid-work/packages/reflex-components-internal/src \
uv run --active --no-sync reflex run --env dev --frontend-port 4192 --backend-port 8192
```

Then run `node runtime-smoke.mjs` from this harness directory. The runtime fixture uses synthetic rows only. Normal setup warnings about the implicit Radix theme/sitemap plugin remain visible in its raw log.

Compact dashboard preview now uses five-row pagination. At 1366/1024×360, `node compact-smoke.mjs` checks that the pager and all five rows fit, then verifies real sort/filter interactions. Budget at least 350–360px iframe height for five rows plus headers, filters, footer and Columns control; a shorter widget should reduce page size or explicitly scroll. The adapter has no data-loading error prop: application-owned error UI remains unimplemented/unverified; validation exceptions are not an error-state design.

The follow-up [current status audit](STATUS-AUDIT.md) supersedes the earlier five-test browser count: eight browser tests now cover accessible status transitions, with 44 affected-package Python tests passing. It also corrects the fixture root package file so the committed fixture starts fresh; see the exact failure/correction evidence rather than treating the earlier running process as proof of fresh-start reproducibility.
