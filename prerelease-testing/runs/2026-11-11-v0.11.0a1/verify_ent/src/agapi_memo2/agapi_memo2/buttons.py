"""The memoized AG Grid API button, defined in a module with no id'd component."""

import reflex as rx

from reflex_enterprise.components.ag_grid.aggrid import AgGridAPI


@rx.memo
def memo_select_button() -> rx.Component:
    """A memoized button calling the grid API by id.

    Returns:
        The button.
    """
    return rx.button("select all (memo)", id="select-memo", on_click=AgGridAPI.create("grid1").select_all())
