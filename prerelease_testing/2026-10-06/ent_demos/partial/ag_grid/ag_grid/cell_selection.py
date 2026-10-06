"""Cell selection demo for AG Grid in Reflex."""

import pandas as pd
import reflex as rx

import reflex_enterprise as rxe

from .common import demo


class CellSelectionState(rx.State):
    """State for the cell selection demo."""

    data: list[dict] = []

    @rx.event
    def load_data(self):
        """Load data into the state."""
        df = pd.read_json(
            "https://raw.githubusercontent.com/ag-grid/ag-grid/7c05eef061914758b1f7334f0d54fa1c578d0c9d/documentation/ag-grid-docs/public/example-assets/small-olympic-winners.json"
        )
        self.data = df.to_dict("records")

    @rx.event
    def echo_selection(self, ranges: list[dict], started: bool, finished: bool):
        """Echo the selected cells."""
        if finished:
            yield rx.toast(f"Selected cells: {ranges}")


column_defs = [
    {"field": "athlete"},
    {"field": "age"},
    {"field": "country"},
    {"field": "year"},
    {"field": "sport"},
    {
        "header_name": "Medals",
        "children": [
            rxe.ag_grid.column_def(
                field="total",
                column_group_show="closed",
                col_id="total",
                value_getter="params.data.gold + params.data.silver + params.data.bronze",
                width=100,
            ),
            {"field": "gold", "column_group_show": "open", "width": 100},
            {"field": "silver", "column_group_show": "open", "width": 100},
            {"field": "bronze", "column_group_show": "open", "width": 100},
        ],
    },
]


@demo(
    route="/cell-selection",
    title="Cell Selection",
    description="Demonstrates cell selection in AG Grid.",
    on_load=CellSelectionState.load_data,
)
def cell_selection_page():
    """Cell selection demo."""
    return rxe.ag_grid(
        id="cell_selection_grid",
        column_defs=column_defs,
        row_data=CellSelectionState.data,
        cell_selection=True,
        on_cell_selection_changed=CellSelectionState.echo_selection,
        width="100%",
        height="600px",
    )
