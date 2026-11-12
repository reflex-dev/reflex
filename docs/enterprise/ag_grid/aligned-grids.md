---
meta_description: "Build aligned grids with AG Grid in Reflex. Synchronize columns and horizontal scrolling across multiple data grids in Python, no JavaScript required."
title: Aligned Grids
---

# Aligned Grids

AgGrid provides a way to align multiple grids together. This is useful when you want to display related data in a synchronized manner.

You can do so through the `aligned_grids` prop. This prop takes a list of grid IDs that you want to align.

```python demo exec
import pandas as pd
import reflex as rx
import reflex_enterprise as rxe

# Olympic winners data (originally from https://www.ag-grid.com/example-assets/olympic-winners.json)
df = pd.read_json("data/olympic-winners.json")

row_data = df.to_dict("records")

column_defs = [
    {"field": "athlete"},
    {"field": "age"},
    {"field": "country"},
    {"field": "year"},
    {"field": "sport"},
    {
        "header_name": "Medals",
        "children": [
            {
                "field": "total",
                "column_group_show": "closed",
                "col_id": "total",
                "value_getter": "params.data.gold + params.data.silver + params.data.bronze",
                "width": 100,
            },
            {"field": "gold", "column_group_show": "open", "width": 100},
            {"field": "silver", "column_group_show": "open", "width": 100},
            {"field": "bronze", "column_group_show": "open", "width": 100},
        ],
    },
]


def aligned_grids_page():
    """Aligned grids demo."""
    return rx.el.div(
        rxe.ag_grid(
            id="grid1",
            column_defs=column_defs,
            row_data=row_data,
            aligned_grids=["grid2"],
            width="100%",
        ),
        rxe.ag_grid(
            id="grid2",
            column_defs=column_defs,
            row_data=row_data,
            aligned_grids=["grid1"],
            width="100%",
        ),
        class_name="flex flex-col gap-y-6 w-full",
    )
```

```python test
def test_expanding_group_in_one_grid_expands_both(demo, page):
    top, bottom = demo.get_by_role("grid").first, demo.get_by_role("grid").last
    expect(bottom.get_by_role("columnheader", name="Gold")).to_have_count(0)
    top.get_by_role("gridcell").first.hover()
    page.mouse.wheel(3000, 0)
    medals = top.locator(".ag-header-group-cell", has_text="Medals")
    medals.locator(".ag-header-expand-icon:visible").click()
    expect(bottom.get_by_role("columnheader", name="Medals")).to_have_attribute(
        "aria-expanded", "true"
    )
    expect(bottom.get_by_role("columnheader", name="Gold")).to_be_visible()
```

```md alert warning
# The pivot functionality does not work with aligned grids. This is because pivoting data changes the columns, which would make the aligned grids incompatible, as they are no longer sharing the same set of columns.
```
