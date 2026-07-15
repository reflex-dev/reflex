---
meta_description: "Enable master-detail rows in AG Grid with Reflex. Expand rows to reveal a nested detail grid backed by per-row data, configured entirely in Python."
title: Master Detail
---

# Master Detail

Master-detail lets rows expand to show detailed information in a nested grid. Each master row carries its detail rows as a nested list, and an expandable column reveals them.

Three pieces are required:

1. `master_detail=True` on the grid.
2. A column with `"cell_renderer": "agGroupCellRenderer"`, which renders the expand/collapse arrows.
3. `detail_cell_renderer_params` describing the detail grid's columns and how to extract the detail rows from the master row.

```python
import reflex as rx
import reflex_enterprise as rxe


class MasterDetailState(rx.State):
    master_data: list[dict] = [
        {
            "id": 1,
            "name": "Product A",
            "category": "Electronics",
            "price": 299.99,
            "counts": [  # Detail rows for this master row
                {"count": 10, "value": "Stock Level"},
                {"count": 5, "value": "Orders Today"},
                {"count": 25, "value": "Total Sales"},
            ],
        },
        {
            "id": 2,
            "name": "Product B",
            "category": "Clothing",
            "price": 49.99,
            "counts": [
                {"count": 50, "value": "Stock Level"},
                {"count": 12, "value": "Orders Today"},
                {"count": 78, "value": "Total Sales"},
            ],
        },
    ]


column_defs = [
    {
        "field": "id",
        "header_name": "ID",
        "width": 80,
        "cell_renderer": "agGroupCellRenderer",  # Required for expand/collapse
    },
    {"field": "name", "header_name": "Product Name", "width": 150},
    {"field": "category", "header_name": "Category", "width": 120},
    {
        "field": "price",
        "header_name": "Price",
        "width": 100,
        "value_formatter": "params.value ? '$' + params.value.toFixed(2) : ''",
    },
]

detail_cell_renderer_params = {
    "detail_grid_options": {
        "column_defs": [
            {"field": "count", "header_name": "Count"},
            {"field": "value", "header_name": "Description"},
        ]
    },
    "get_detail_row_data": lambda params: rx.vars.function.FunctionStringVar(
        "params.successCallback"
    ).call(params.data.counts),
}


def master_detail_grid():
    return rxe.ag_grid(
        id="master_detail_grid",
        row_data=MasterDetailState.master_data,
        column_defs=column_defs,
        master_detail=True,
        detail_cell_renderer_params=detail_cell_renderer_params,
        width="100%",
        height="500px",
    )
```

## How Detail Rows Are Provided

`get_detail_row_data` follows AG Grid's asynchronous convention: the grid passes a `params` object containing the master row's `data` and a `successCallback` to invoke with the detail rows. The lambda above calls `params.successCallback` with the nested `counts` list of the expanded row.

The detail grid is a full AG Grid instance with its own `column_defs`, independent from the master grid's columns.

## Static vs State Configuration

Both the column definitions and the detail renderer params can be plain module-level objects or state vars, depending on whether they need to change at runtime:

```python
STATIC_DETAIL_PARAMS = {
    "detail_grid_options": {"column_defs": [{"field": "count"}]},
    "get_detail_row_data": lambda params: rx.vars.function.FunctionStringVar(
        "params.successCallback"
    ).call(params.data.counts),
}


class State(rx.State):
    # Dynamic variant: update these vars to reconfigure the grid
    detail_cell_renderer_params: dict = STATIC_DETAIL_PARAMS
```
