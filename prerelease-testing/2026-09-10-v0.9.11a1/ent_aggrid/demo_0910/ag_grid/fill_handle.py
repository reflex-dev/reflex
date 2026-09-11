"""Fill Handle demo for AG Grid in Reflex."""

from typing import Any, TypedDict

import reflex as rx

import reflex_enterprise as rxe

from .common import demo


class DataRow(TypedDict):
    """Data row type for AG Grid."""

    athlete: str
    age: int | None
    country: str
    year: int | None
    date: str
    sport: str
    gold: int
    silver: int
    bronze: int
    total: int


class FillHandleState(rx.State):
    """State for the fill handle demo."""

    # Sample Olympic data similar to AG Grid's example
    row_data: list[DataRow] = [
        {
            "athlete": "Michael Phelps",
            "age": 23,
            "country": "United States",
            "year": 2008,
            "date": "24/08/2008",
            "sport": "Swimming",
            "gold": 8,
            "silver": 0,
            "bronze": 0,
            "total": 8,
        },
        {
            "athlete": "Michael Phelps",
            "age": 19,
            "country": "United States",
            "year": 2004,
            "date": "29/08/2004",
            "sport": "Swimming",
            "gold": 6,
            "silver": 0,
            "bronze": 2,
            "total": 8,
        },
        {
            "athlete": "Michael Phelps",
            "age": 27,
            "country": "United States",
            "year": 2012,
            "date": "12/08/2012",
            "sport": "Swimming",
            "gold": 4,
            "silver": 2,
            "bronze": 0,
            "total": 6,
        },
        {
            "athlete": "Natalie Coughlin",
            "age": 25,
            "country": "United States",
            "year": 2008,
            "date": "24/08/2008",
            "sport": "Swimming",
            "gold": 1,
            "silver": 2,
            "bronze": 3,
            "total": 6,
        },
        {
            "athlete": "Aleksey Nemov",
            "age": 24,
            "country": "Russia",
            "year": 2000,
            "date": "01/10/2000",
            "sport": "Gymnastics",
            "gold": 2,
            "silver": 1,
            "bronze": 3,
            "total": 6,
        },
        {
            "athlete": "Alicia Coutts",
            "age": 24,
            "country": "Australia",
            "year": 2012,
            "date": "12/08/2012",
            "sport": "Swimming",
            "gold": 1,
            "silver": 3,
            "bronze": 1,
            "total": 5,
        },
        {
            "athlete": "Missy Franklin",
            "age": 17,
            "country": "United States",
            "year": 2012,
            "date": "12/08/2012",
            "sport": "Swimming",
            "gold": 4,
            "silver": 0,
            "bronze": 1,
            "total": 5,
        },
        {
            "athlete": "Ryan Lochte",
            "age": 27,
            "country": "United States",
            "year": 2012,
            "date": "12/08/2012",
            "sport": "Swimming",
            "gold": 2,
            "silver": 2,
            "bronze": 1,
            "total": 5,
        },
        {
            "athlete": "Allison Schmitt",
            "age": 22,
            "country": "United States",
            "year": 2012,
            "date": "12/08/2012",
            "sport": "Swimming",
            "gold": 3,
            "silver": 1,
            "bronze": 1,
            "total": 5,
        },
        {
            "athlete": "Natalie Coughlin",
            "age": 21,
            "country": "United States",
            "year": 2004,
            "date": "29/08/2004",
            "sport": "Swimming",
            "gold": 2,
            "silver": 2,
            "bronze": 1,
            "total": 5,
        },
    ]

    @rx.event
    def on_cell_value_changed(self, params: dict[str, Any]):
        """Handle cell value changes from fill handle operations."""
        row_index = int(params["node_id"])
        field = params["field"]
        new_value = params["newValue"]

        # Convert numeric fields appropriately
        if field in ["age", "year", "gold", "silver", "bronze", "total"]:
            try:
                new_value = int(new_value) if new_value else None
            except (ValueError, TypeError):
                new_value = None

        # Update the row data in the state
        self.row_data[row_index][field] = new_value

        return rx.toast(f"Updated {field}: {new_value}")


# Column definitions based on the AG Grid reference
column_defs = [
    {
        "field": "athlete",
        "width": 150,
        "suppress_fill_handle": True,  # Text fields typically don't use fill handle
    },
    {
        "field": "age",
        "width": 90,
        "editable": True,
    },
    {
        "field": "country",
        "width": 120,
        "suppress_fill_handle": True,  # Country names shouldn't be filled
    },
    {
        "field": "year",
        "width": 90,
        "editable": True,
    },
    {
        "field": "date",
        "width": 110,
        "editable": True,  # Enable editing and fill handle for dates
    },
    {
        "field": "sport",
        "width": 110,
        "suppress_fill_handle": True,  # Sport names shouldn't be filled
    },
    {
        "field": "gold",
        "width": 100,
        "editable": True,
        "type": "numericColumn",
    },
    {
        "field": "silver",
        "width": 100,
        "editable": True,
        "type": "numericColumn",
    },
    {
        "field": "bronze",
        "width": 100,
        "editable": True,
        "type": "numericColumn",
    },
    {
        "field": "total",
        "width": 100,
        "editable": True,
        "type": "numericColumn",
    },
]


@demo(
    route="/fill-handle",
    title="Fill Handle",
    description="Demonstrates the Fill Handle feature. Select cells and drag the fill handle (small square in bottom-right corner) to copy values or create series.",
)
def fill_handle_page():
    """Fill handle demo page."""
    return rx.vstack(
        rx.heading("Fill Handle Demo", size="6", margin_bottom="1em"),
        rx.text(
            "How to use the Fill Handle:",
            font_weight="bold",
            margin_bottom="0.5em",
        ),
        rx.unordered_list(
            rx.list_item("Select a cell or range of cells"),
            rx.list_item(
                "Look for the small square (fill handle) in the bottom-right corner"
            ),
            rx.list_item("Drag the fill handle to extend the selection"),
            rx.list_item("For numbers: Creates incremental series (1, 2, 3...)"),
            rx.list_item("For dates: Copies the date value to adjacent cells"),
            rx.list_item("For single values: Copies the value to all selected cells"),
            rx.list_item("Try with different data types (age, year, dates, medals)"),
            margin_bottom="1em",
        ),
        rx.text(
            "Note: Fill handle is disabled only for text fields like athlete, country, and sport to show selective control.",
            color="gray",
            font_size="sm",
            margin_bottom="1em",
        ),
        rxe.ag_grid(
            id="fill-handle-grid",
            column_defs=column_defs,
            row_data=FillHandleState.row_data,
            on_cell_value_changed=FillHandleState.on_cell_value_changed,
            # Configure cell selection with fill handle - single cell only
            cell_selection={
                "mode": "singleCell",  # Only allow single cell selection
                "handle": {
                    "mode": "fill",  # Enable fill handle
                    "direction": "xy",  # Allow both horizontal and vertical filling
                },
            },
            width="100%",
            height="500px",
        ),
        width="100%",
    )
