"""Grid State Serialization Example."""

import json

import pandas as pd
import reflex as rx

import reflex_enterprise as rxe

from .common import demo

data_url = "https://raw.githubusercontent.com/ag-grid/ag-grid/7c05eef061914758b1f7334f0d54fa1c578d0c9d/documentation/ag-grid-docs/public/example-assets/small-olympic-winners.json"


class GridSerializationState(rx.State):
    """State for the grid serialization example."""

    grid_state: str = rx.LocalStorage()

    grid_state_backend: list = []

    row_data: list = []

    @rx.event
    def load_data(self):
        """Load data from the URL."""
        self.row_data = pd.read_json(data_url).to_dict("records")

    @rx.event
    def save_state(self, state_data: list):
        """Save the columns state to local storage."""
        self.grid_state = json.dumps(state_data)

    @rx.event
    def save_state_backend(self, state_data: list):
        """Save the columns state to the backend."""
        self.grid_state_backend = state_data

    @rx.var
    def column_state(self) -> list:
        """Get the column state from local storage."""
        return json.loads(self.grid_state) if self.grid_state else []


@demo(
    route="/simple-serialization",
    title="Grid State Serialization (Simple)",
    description="AG Grid with column state serialization.",
    on_load=GridSerializationState.load_data,
)
def grid_state_serialization_simple_page():
    """Grid State Serialization Example."""
    # We define the grid here to be able to access it's .api outside the grid.
    grid = rxe.ag_grid(
        id="grid_serialization",
        column_defs=[
            {"field": "athlete"},
            {"field": "age", "value_formatter": "params.value + ' years old'"},
            {"field": "country"},
            {"field": "year"},
        ],
        row_data=GridSerializationState.row_data,
        width="100%",
    )
    # Use grid.api.get_column_state() to get the column state and save it to local storage / backend.
    return rx.vstack(
        rx.hstack(
            rx.button(
                "Save State",
                on_click=[
                    grid.api.get_column_state(  # pyright: ignore [reportAttributeAccessIssue]
                        callback=GridSerializationState.save_state
                    ),
                    rx.toast("State saved"),
                ],
            ),
            rx.button(
                "Restore State",
                on_click=[
                    grid.api.apply_column_state(  # pyright: ignore [reportAttributeAccessIssue]
                        {"state": GridSerializationState.column_state}
                    ),
                    rx.toast("State restored"),
                ],
            ),
            rx.button(
                "Save State Backend",
                on_click=[
                    grid.api.get_column_state(  # pyright: ignore [reportAttributeAccessIssue]
                        callback=GridSerializationState.save_state_backend
                    ),
                    rx.toast("State saved to backend"),
                ],
            ),
            rx.button(
                "Restore State Backend",
                on_click=[
                    grid.api.apply_column_state(  # pyright: ignore [reportAttributeAccessIssue]
                        {"state": GridSerializationState.grid_state_backend}
                    ),
                    rx.toast("State restored from backend"),
                ],
            ),
        ),
        grid,  # Finally, don't forget to add the grid to the layout.
    )
