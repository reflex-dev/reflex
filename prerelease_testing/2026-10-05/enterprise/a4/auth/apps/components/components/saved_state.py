"""Grid State Serialization Example."""

import json
from typing import Any

import reflex_enterprise as rxe

import reflex as rx

from .common import demo

column_defs = [
    {"field": "athlete", "minWidth": 150, "filter": True},
    {"field": "age", "maxWidth": 90},
    {"field": "country", "minWidth": 150},
    {"field": "year", "maxWidth": 90},
    {"field": "date", "minWidth": 150},
    {"field": "sport", "minWidth": 150},
    {"field": "gold"},
    {"field": "silver"},
    {"field": "bronze"},
    {"field": "total"},
]

default_column_def = {
    "flex": 1,
    "minWidth": 100,
    "filter": True,
    "enableRowGroup": True,
    "enablePivot": True,
    "enableValue": True,
}


class GridSerializationAdvancedState(rx.State):
    """State for the advanced grid serialization example."""

    grid_state: str = rx.LocalStorage()

    row_data: list[dict] = []

    @rx.event
    def load_data(self):
        """Load deterministic local records for browser state persistence checks."""
        self.row_data = [
            {
                "athlete": "Alpha",
                "age": 31,
                "country": "United Kingdom",
                "year": 2024,
                "sport": "Swimming",
                "gold": 1,
            },
            {
                "athlete": "Beta",
                "age": 21,
                "country": "France",
                "year": 2024,
                "sport": "Swimming",
                "gold": 2,
            },
            {
                "athlete": "Gamma",
                "age": 41,
                "country": "United States",
                "year": 2024,
                "sport": "Running",
                "gold": 3,
            },
            {
                "athlete": "Delta",
                "age": 25,
                "country": "Canada",
                "year": 2024,
                "sport": "Running",
                "gold": 4,
            },
        ]

    @rx.event
    def save_state(self, state_data: Any):
        """Save the columns state to local storage."""
        self.grid_state = json.dumps(state_data["state"])

    @rx.var
    def grid_state_dict(self) -> dict:
        """Get the grid state from local storage."""
        return json.loads(self.grid_state) if self.grid_state else {}


@demo(
    route="/advanced-serialization",
    title="Grid State Serialization (Advanced)",
    description="AG Grid with column state serialization.",
    on_load=GridSerializationAdvancedState.load_data,
)
def grid_state_serialization_advanced_page():
    """Grid State Serialization Advanced Example."""
    grid = rxe.ag_grid(
        id="grid_serialization_advanced",
        column_defs=column_defs,
        default_column_def=default_column_def,
        row_data=GridSerializationAdvancedState.row_data,
        side_bar=True,
        pagination=True,
        row_selection={"mode": "multiRow"},
        suppress_column_move_animation=True,
        initial_state=GridSerializationAdvancedState.grid_state_dict,
        on_state_updated=GridSerializationAdvancedState.save_state,
        community_modules={"NumberFilterModule"},
        enterprise_modules={"FiltersToolPanelModule"},
        width="100%",
        height="600px",
    )
    return rx.vstack(
        rx.hstack(
            rx.cond(
                rx.State.is_hydrated, grid
            ),  # Finally, don't forget to add the grid to the layout.
            width="100%",
        ),
        width="100%",
    )
