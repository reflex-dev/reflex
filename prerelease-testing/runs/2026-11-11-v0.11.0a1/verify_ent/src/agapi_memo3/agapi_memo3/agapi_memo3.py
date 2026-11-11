"""Issue 3 variant: the AG Grid API call lives in an @rx.memo component defined in another module."""

import reflex as rx

import reflex_enterprise as rxe
from .buttons import memo_select_button

ROWS = [{"make": "Tesla", "price": 1}, {"make": "Ford", "price": 2}, {"make": "Kia", "price": 3}]




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
