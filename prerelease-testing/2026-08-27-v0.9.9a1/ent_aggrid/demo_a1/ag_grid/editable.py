"""Editable AG Grid Example."""

from typing import TypedDict

import reflex as rx

import reflex_enterprise as rxe

from .common import demo


class Person(TypedDict):
    """Person type for AG Grid."""

    name: str
    age: int
    country: str


class EditableState(rx.State):
    """State for the editable demo."""

    # This state is used to store the data for the AG Grid.
    row_data: list[Person] = [
        {"name": "John", "age": 30, "country": "USA"},
        {"name": "Anna", "age": 25, "country": "Sweden"},
        {"name": "Mike", "age": 35, "country": "Canada"},
    ]

    @rx.event
    def on_cell_value_changed(self, params: dict[str, str]):
        """Handle cell value changes."""
        # We use node_id which represent the initial position of the changed row in the dataset.
        # rowIndex is the index of the row in the grid, which may change if the grid is sorted or filtered.
        row_index = int(params["node_id"])
        field = params["field"]
        new_value = params["newValue"]

        # Update the row data in the state.
        self.row_data[row_index][field] = new_value

        # Show a toast message with the updated value.
        return rx.toast(f"Cell value changed: {field} = {new_value}")


column_defs = [
    {"header_name": "Name", "field": "name", "editable": True},
    {"header_name": "Age", "field": "age", "editable": True},
    {"header_name": "Country", "field": "country", "editable": True},
]


@demo(
    route="/editable",
    title="Editable AG Grid",
    description="An editable AG Grid example.",
)
def editable_page():
    """Editable AG Grid example page."""
    return rxe.ag_grid(
        id="editable-grid",
        column_defs=column_defs,
        row_data=EditableState.row_data,  # pyright: ignore [reportArgumentType],
        on_cell_value_changed=EditableState.on_cell_value_changed,  # pyright: ignore [reportArgumentType],
    )
