```python exec
import reflex as rx
import reflex_enterprise as rxe
from pcweb.pages.docs import enterprise
```

# Pivot Mode

Pivot mode allows you to visualize your data in a different way than how they are originally structured in the data source. When pivoting on a column, the values in that column will be used as column headers. This allows you to see the data in a more compact way, and can be useful when you have a lot of data to display.

To enable pivot mode, set the `pivot_mode` property to `True` in the grid props. Once pivot mode is enabled, you can define which column to pivot on by setting the `pivot` property in a column definition. In addition to the pivot column, at least one column definition must have `row_group` property set to `True` to define the row grouping.

You can also define how rows are aggregated by passing the `agg_func` property in the column definition. The `agg_func` property should be set to a string that represents the aggregation function to use. The built-in aggregation functions are `sum`, `min`, `max`, `count`, `avg`, `first`, and `last`.

You can find a live example here: [Pivot Mode Example](https://aggrid.reflex.run/pivot).

```python demo exec
import pandas as pd
import reflex as rx

import reflex_enterprise as rxe

# Olympic winners data (originally from https://www.ag-grid.com/example-assets/olympic-winners.json)
df = pd.read_json("data/olympic-winners.json")

def pivot_page():
    return rxe.ag_grid(
        id="sandbox_grid",
        column_defs=[
            {"field": "country", "row_group": True},
            {"field": "sport", "pivot": True},
            {"field": "year", "pivot": True},
            {"field": "gold", "aggFunc": "sum"},
        ],
        loading=False,
        row_data=df.to_dict("records"),
        default_col_def={
            "flex": 1,
            "min_width": 130,
            "enable_value": True,
            "enable_row_group": True,
            "enable_pivot": True,
        },
        auto_group_column_def={
            "minWidth": 200,
            "pinned": "left",
        },
        pivot_mode=True,
        side_bar="columns",
        pivot_panel_show="always",
        width="100%",
        height="500px",
        ),
```

# Pivot using State

```python demo exec
import pandas as pd
import reflex as rx

import reflex_enterprise as rxe

df = pd.read_csv("data/wind_dataset.csv")


class PivotState(rx.State):
    """State for the sandbox page."""

    pivot = False
    row_grouping = False

    @rx.event
    def toggle_pivot(self):
        """Toggle the pivot."""
        self.pivot = not self.pivot

    @rx.event
    def toggle_row_grouping(self):
        """Toggle the row grouping."""
        self.row_grouping = not self.row_grouping


def sandbox_page():
    """Sandbox page."""
    return rx.vstack(
        rx.hstack(
            rx.text("Toggle Pivot"),
            rx.switch(
                on_click=PivotState.toggle_pivot,
                name="pivot",
                checked=PivotState.pivot,
            ),
            rx.text("Toggle Row Grouping"),
            rx.switch(
                on_click=PivotState.toggle_row_grouping,
                name="row_grouping",
                checked=PivotState.row_grouping,
            )
        ),
        rxe.ag_grid(
            id="sandbox_grid",
            column_defs=[
                rxe.ag_grid.column_def(
                    field="direction",
                    pivot=True,
                ),
                rxe.ag_grid.column_def(
                    field="strength",
                ),
                rxe.ag_grid.column_def(
                    field="frequency",
                    agg_func="count",
                    row_group=PivotState.row_grouping,
                ),
            ],
            row_data=df.to_dict("records"),
            pivot_mode=PivotState.pivot,
            pivot_panel_show="onlyWhenPivoting",
            width="100%",
            height="500px",
        ),
        width="100%",
    )

```

📊 **Dataset source:** [wind_dataset.csv](https://raw.githubusercontent.com/plotly/datasets/master/wind_dataset.csv)


