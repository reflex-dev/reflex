"""Example of handling grid selection events and displaying selected items in a separate panel."""

import pandas as pd
import reflex as rx

import reflex_enterprise as rxe

from .common import demo

df = pd.read_csv(
    "https://raw.githubusercontent.com/plotly/datasets/master/wind_dataset.csv"
)

column_defs = [
    rxe.ag_grid.column_def(field="direction"),  # pyright: ignore [reportCallIssue]
    rxe.ag_grid.column_def(field="strength"),  # pyright: ignore [reportCallIssue]
    rxe.ag_grid.column_def(field="frequency"),  # pyright: ignore [reportCallIssue]
]


class BasicGridState(rx.State):
    """State for the basic grid example."""

    selection: list[dict[str, str]] = []

    @rx.event
    def set_selection(self, selection: list[dict[str, str]]):
        """Set the selection."""
        self.selection = selection

    keys: list[str] = []

    @rx.event
    def set_keys(self, keys: list[str]):
        self.keys = [k.upper() for k in keys]
        return type(self).select_by_direction

    @rx.event
    def select_by_direction(self):
        return grid_api.select_rows_by_key(self.keys, node_path_key="data.direction")


grid = rxe.ag_grid(
    id="ag_grid_basic_1",
    row_data=df.to_dict("records"),  # pyright: ignore [reportArgumentType]
    column_defs=column_defs,  # pyright: ignore [reportArgumentType]
    row_selection={"mode": "multiRow"},
    on_selection_changed=lambda rows, _0, _1: BasicGridState.set_selection(rows),  # pyright: ignore [reportArgumentType]
    width="50%",
    height="71vh",
)
grid_api = rxe.ag_grid.api("ag_grid_basic_1")


def selected_item(item: dict[str, str]) -> rx.Component:
    """Create a selected item component."""
    return rx.card(
        rx.data_list.root(
            rx.foreach(
                item,
                lambda kv: rx.data_list.item(
                    rx.data_list.label(kv[0]),
                    rx.data_list.value(kv[1]),
                ),
            ),
        ),
    )


@demo(
    route="/selected-items",
    title="Selected Items",
    description="Handle grid selection events and display selected items in a separate panel.",
)
def selected_items_example():
    """Selected items example."""
    return rx.hstack(
        rx.vstack(
            rx.text("Select by Direction"),
            rxe.mantine.tags_input(
                value=BasicGridState.keys,
                allow_duplicates=False,
                on_change=BasicGridState.set_keys,
                width="10vw",
            ),
            rx.button(
                "Select All",
                on_click=[grid_api.select_all],  # pyright: ignore [reportAttributeAccessIssue]
            ),
            rx.button(
                "Deselect All",
                on_click=[grid_api.deselect_all, BasicGridState.set_keys([])],  # pyright: ignore [reportAttributeAccessIssue]
            ),
            rx.button("Log nodes", on_click=grid_api.log_nodes("data")),
        ),
        grid,
        rx.vstack(
            rx.heading(
                f"Selected Items ({BasicGridState.selection.length()})",  # pyright: ignore [reportAttributeAccessIssue]
                size="4",
            ),
            rx.scroll_area(
                rx.hstack(
                    rx.foreach(
                        BasicGridState.selection,
                        selected_item,
                    ),
                    wrap="wrap",
                ),
            ),
            max_width="48%",
            height="71vh",
        ),
        width="100%",
    )
