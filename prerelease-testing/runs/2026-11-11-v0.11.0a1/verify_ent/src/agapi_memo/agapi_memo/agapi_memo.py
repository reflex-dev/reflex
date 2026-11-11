"""Issue 3 variant: the AG Grid API call lives in an @rx.memo component (its own JS module)."""

import reflex as rx

import reflex_enterprise as rxe
from reflex_enterprise.components.ag_grid.aggrid import AgGridAPI

ROWS = [{"make": "Tesla", "price": 1}, {"make": "Ford", "price": 2}, {"make": "Kia", "price": 3}]


@rx.memo
def memo_select_button() -> rx.Component:
    """A memoized button calling the grid API by id.

    Returns:
        The button.
    """
    return rx.button("select all (memo)", id="select-memo", on_click=AgGridAPI.create("grid1").select_all())


def index() -> rx.Component:
    return rx.vstack(
        rxe.ag_grid(
            id="grid1",
            row_data=ROWS,
            column_defs=[{"field": "make"}, {"field": "price"}],
            row_selection={"mode": "multiRow"},
            width="400px",
            height="300px",
        ),
        memo_select_button(),
    )


app = rxe.App()
app.add_page(index)
