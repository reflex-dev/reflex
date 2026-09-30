---
title: "AG Grid changes in reflex-enterprise 0.9.7"
meta_description: "Prepare for reflex-enterprise 0.9.7, which upgrades AG Grid to 36.2.0, with migration notes for CSS, overlays, columns, filters, saved state, and charts."
---

# AG Grid changes in reflex-enterprise 0.9.7

The upcoming **reflex-enterprise 0.9.7** release upgrades AG Grid from **34.3.1** to **36.2.0**, with integrated AG Charts moving from **11.2.4** to **14.2.0**. This guide covers the changes to review when upgrading your app to reflex-enterprise 0.9.7.

The wrapper pins `ag-grid-react`, `ag-grid-community`, and `ag-grid-enterprise` to the same version, and pairs them with `ag-charts-enterprise` 14.2.0. AG Grid installs its new `ag-stack` dependency transitively. Remove conflicting AG Grid or Charts versions from your app's frontend package configuration.

## Themes and custom CSS

Existing `theme="quartz"`, `"alpine"`, `"balham"`, and `"material"` settings continue to use [legacy CSS themes](/docs/enterprise/ag-grid/theme/), including Reflex color-mode selection. The wrapper has not switched to the new Theming API.

AG Grid 36 replaces the separate scrolling and pinned containers with a shared scrolling layout. It also moves theme and RTL classes onto parent elements. Update custom CSS and browser tests that depend on the old containers. Common selector changes include:

| Previous selector | Replacement |
| --- | --- |
| `.ag-body-viewport` | `.ag-grid-scrolling-container` |
| `.ag-center-cols-container` | `.ag-grid-scrolling-cells` |
| `.ag-pinned-left-cols-container` | `.ag-grid-scrolling-rows .ag-grid-pinned-left-cells` |
| `.ag-floating-top-container` | `.ag-grid-pinned-top-rows-container` |
| `.ag-root-wrapper.ag-rtl` | `.ag-rtl .ag-root-wrapper` |

See the complete [v36 DOM migration reference](https://www.ag-grid.com/react-data-grid/upgrading-to-ag-grid-36/#dom-structure-migration-reference) for other changed or removed containers.

## Overlays

Filtering to zero matches now displays a “No Matching Rows” overlay, and exports started through the grid UI display an exporting overlay. Infinite and server-side grids also display empty-data overlays.

To suppress the new filtering and exporting overlays, set `suppress_overlays` when creating the grid:

```python
import reflex_enterprise as rxe

rxe.ag_grid(
    id="inventory",
    column_defs=[{"field": "name", "filter": True}],
    row_data=[{"name": "Alpha"}],
    suppress_overlays=["noMatchingRows", "exporting"],
)
```

This is an **initial-only** option; it cannot be changed through `api.set_grid_option` after the grid is created. Other supported overlay names are `"loading"`, `"noRows"`, and `"fileInput"`.

## Column definitions and sizing

Setting `suppress_auto_size` on a column now disables every auto-sizing mechanism for that column, including API calls, the column menu, and double-clicking the column divider.

`cellDataType` inside `column_types` and `colId` inside `auto_group_column_def` were ignored upstream and are no longer supported in those locations. Set cell data types on actual column definitions. Use the auto-group column's `context` for application metadata.

In v36.2, upstream deprecates `tooltipField`, `tooltipValueGetter`, and `headerTooltipValueGetter`; they remain supported. Consult the [v36.2 guide](https://www.ag-grid.com/react-data-grid/upgrading-to-ag-grid-36-2/) before changing custom JavaScript tooltip configuration.

## Filters and saved state

For columns using `cellDataType="date"`, filter models now contain date-only values. Check application code that reads or restores those values.

The order of value columns in the columns tool panel is now included in grid state. Restoring state preserves the corresponding pivot-result header order.

## Integrated charts

Review custom chart themes and options when moving from AG Charts 11.2.4 to 14.2.0. The [v12](https://www.ag-grid.com/charts/react/upgrade-to-ag-charts-12/), [v13](https://www.ag-grid.com/charts/react/upgrade-to-ag-charts-13/), and [v14](https://www.ag-grid.com/charts/react/upgrade-to-ag-charts-14/) guides describe the changes, including replacements for removed highlight and palette options.

Charts no longer implicitly use a row-group column for grouped categories. Set `useGroupColumnAsCategory: true` in the chart creation options when you need that behavior.

## Wrapper compatibility fixes

The upgrade also fixes these wrapper behaviors:

- `row_id_key` generates a JavaScript function returning the row's ID, allowing selection and editing to identify rows correctly.
- `pinned_top_row_data` and `pinned_bottom_row_data` use the correct upstream prop names. The original `pinned_row_top_data` and `pinned_row_bottom_data` spellings remain supported as aliases.
- Infinite and server-side datasource URLs preserve query parameters, including pagination and sorting parameters.

The wrapper continues to register `ValidationModule` explicitly in development. AG Grid 36 no longer includes it in the all-modules bundles, but development diagnostics remain available in Reflex apps.

See the complete upstream guides for [v35](https://www.ag-grid.com/react-data-grid/upgrading-to-ag-grid-35/), [v36](https://www.ag-grid.com/react-data-grid/upgrading-to-ag-grid-36/), [v36.1](https://www.ag-grid.com/react-data-grid/upgrading-to-ag-grid-36-1/), and [v36.2](https://www.ag-grid.com/react-data-grid/upgrading-to-ag-grid-36-2/). Neither v35 nor v36 removes deprecated Grid APIs.
