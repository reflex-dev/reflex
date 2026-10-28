# Experimental original table

`reflex_components_internal.experimental.native_table` is a read-only, original semantic HTML table prototype. It uses React already provided by Reflex and introduces no AG Grid packages. It is a separate comparison, not an AG Grid API clone or a replacement for the dependable Community adapter. No AG Grid implementation source was used to write it.

```python
from reflex_components_internal.experimental.native_table import native_table

native_table(
    rows=[{"id": "project-a", "project": "Website", "budget": 12000}],
    columns=[
        {"key": "project", "label": "Project", "width": 250},
        {"key": "budget", "label": "Budget", "type": "number"},
    ],
    page_size=25,
)
```

Rows require unique nonempty string or finite number IDs under `row_id_key` (default `id`). String and number IDs sharing the same string form are duplicates. Column keys must be unique nonempty strings. Columns accept `key`, `label`, `type` (`text` or `number`) and `width` (90–480 CSS pixels, default 180). Values are rendered as plain text. Supply finite numbers for numeric sorting; null and nonnumeric values sort last in either direction. Rows and column definitions should be replaced immutably when changed.

| Capability | MVP behavior |
|---|---|
| Sort | One column; ascending, descending, then source order. Stable ties; natural text comparison uses the browser locale. |
| Filter | One case-insensitive text search across all declared columns, including hidden columns. |
| Column visibility/order | Native controls in a nonmodal Columns section; at least one visible column. |
| Resize | Keyboard/pointer native width sliders; no column-edge drag. |
| Selection | Multi-checkbox selection by stable ID, preserved across filtering/pages. Removed rows prune selection and notify `on_selection_changed`; reintroduced IDs start unselected. |
| Pagination | Client-side fixed `page_size`; only the current page is rendered. |
| Keyboard | Native search/button/checkbox/range controls, sortable header buttons, semantic table headers and `aria-sort`. No spreadsheet cell-arrow navigation. |
| States | Explicit loading/error messages, empty data and empty filter results. |
| Responsive | Horizontal overflow stays inside the table; column controls wrap. |
| Styling | Inherits `--font-sans`, `--secondary-*`, `--primary-*` and `--radius-ui-md` with fallbacks. |

Not implemented: pinned columns, virtualization, range selection, editable cells, drag column reorder, typed per-column filter menus, grouping, pivoting, aggregates, CSV/Excel export, server-side rows, persisted/controlled state or Enterprise behavior. Selection/layout are local presentation state. There are no business-write handlers. This experimental module is deliberately absent from the package root exports.

The filter and sort run over the entire client-side dataset. Pagination bounds DOM rows; it is **not virtualization**. The 10,000-row deterministic browser fixture proves functional behavior at that size, not a maximum supported scale or a speed advantage. Separate raw helper timing samples are recorded in the cloud evidence directory and exclude React, DOM, compilation and transport.

## Reproduce the cloud evidence

From the isolated `/workspace/table-work` checkout:

```bash
UV_CACHE_DIR=/workspace/.cache/uv \
UV_PROJECT_ENVIRONMENT=/workspace/reflex/.venv \
PYTHONPATH="$PWD/packages/reflex-components-internal/src" \
uv run --no-sync pytest tests/units/reflex_components_internal -q
node --test tests/units/reflex_components_internal/experimental/native_table_model.test.mjs
```

The cloud source harness `/workspace/table-preview` imports the exact `NativeTable.js` and `nativeTableModel.js` files. `npm ci && npm run dev` starts it at `http://127.0.0.1:3421`; `node verify.mjs` drives actual system Chromium, emits normal/responsive screenshots and verifies sorting, filtering, column controls, ID-based selection, row-removal updates and loading/error/empty states. `node benchmark.mjs` records model-only raw samples with runtime/CPU metadata. This harness is review evidence, not a production deployment or full compiled Reflex integration test.

## Tradeoffs and remaining review

A native table keeps markup and behavior easy to inspect, supports ordinary browser accessibility and has a small dependency footprint. Its client-side processing, limited keyboard model and missing virtualization make it less suitable than AG Grid for complex or very large interactive datasets. The Community adapter remains the practical choice when those capabilities matter.

The UI uses actual source renderers and synthetic data. Shared theme provenance is `reflex-dev/reflex` base `17370c28` and consuming `reflex-dev/flexgen` base `ab8bec51`; it does not copy the documentation-site theme. Dark mode, screen-reader combinations, full compiled Reflex application integration and large-data behavior require further verification before a stable release.
