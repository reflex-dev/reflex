"""Demo of AgGrid defining columns and data in the state."""

from typing import Any

import pandas as pd
import reflex as rx

import reflex_enterprise as rxe

from .common import demo

df = pd.read_csv(
    "https://raw.githubusercontent.com/plotly/datasets/master/wind_dataset.csv"
)


class GridState(rx.State):
    """State for the AGGrid with data and column definitions."""

    column_defs: list[dict[str, Any]]
    row_data: list[dict[str, Any]]
    select_all_on_load: bool = False

    @rx.event
    def set_select_all_on_load(self, value: bool):
        """Set the select_all_on_load flag."""
        self.select_all_on_load = value

    @rx.event
    def load_columns(self):
        """Load columns into the state."""
        self.column_defs = [
            {"field": "direction", "header_name": "DIR"},
            {"field": "strength", "headerName": "STR"},
            {
                "field": "frequency",
                "header_name": "HZ",
                "value_formatter": "params.value + ' Hz'",
            },
        ]

    @rx.event
    def load_data(self):
        """Load columns and data into the state."""
        self.row_data = df.to_dict("records")

    @rx.event
    def clear_columns(self):
        """Clear the columns from the state."""
        self.column_defs = []

    @rx.event
    def clear_data(self):
        """Clear the data from the state."""
        self.row_data = []


@demo(
    route="/state-grid",
    title="AGGrid w/ State",
    description="AGGrid with data and column definitions in the state.",
)
def state_grid_page():
    """AGGrid with data and column definitions in the state."""
    return rx.container(
        rx.hstack(
            rx.button("Load Columns", on_click=GridState.load_columns),
            rx.button("Load Data", on_click=GridState.load_data),
            rx.vstack(
                rx.text("Select All on Load", size="1"),
                rx.switch(
                    checked=GridState.select_all_on_load,
                    on_change=GridState.set_select_all_on_load,
                ),
                align="center",
                justify="center",
            ),
            rx.button("Clear Columns", on_click=GridState.clear_columns),
            rx.button("Clear Data", on_click=GridState.clear_data),
            padding_bottom="25px",
        ),
        rxe.ag_grid(
            id="ag_grid_state",
            column_defs=GridState.column_defs,
            row_data=GridState.row_data,
            row_selection={
                "mode": "multiRow",
            },
            on_row_data_updated=[
                rx.cond(
                    GridState.select_all_on_load,
                    rxe.ag_grid.api(id="ag_grid_state").select_all(),
                    rx.noop(),
                ),
                GridState.set_select_all_on_load(False),
            ],
            width="100%",
            height="71vh",
        ),
    )
