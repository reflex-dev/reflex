"""Demonstrates the use of aligned grids in Reflex."""

import pandas as pd
import reflex as rx

import reflex_enterprise as rxe

from .common import demo


class AlignedState(rx.State):
    """State for the aligned grids demo."""

    data: list[dict] = []

    @rx.event
    def load_data(self):
        """Load data into the state."""
        df = pd.read_json(
            "https://raw.githubusercontent.com/ag-grid/ag-grid/7c05eef061914758b1f7334f0d54fa1c578d0c9d/documentation/ag-grid-docs/public/example-assets/small-olympic-winners.json"
        )
        self.data = df.to_dict("records")


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
    route="/aligned-grids",
    title="Aligned Grids",
    description="Demonstrates the use of aligned grids in Reflex.",
    on_load=AlignedState.load_data,
)
def aligned_grids_page():
    """Aligned grids demo."""
    return rxe.ag_grid(
        id="grid1",
        column_defs=column_defs,
        row_data=AlignedState.data,
        aligned_grids=["grid2"],
        width="100%",
    ), rxe.ag_grid(
        id="grid2",
        column_defs=column_defs,
        row_data=AlignedState.data,
        aligned_grids=["grid1"],
        width="100%",
    )
