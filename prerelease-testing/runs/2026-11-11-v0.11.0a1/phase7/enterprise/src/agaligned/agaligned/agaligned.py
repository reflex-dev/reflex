"""Issue 3 variant: aligned_grids (rxe AgGrid._format_props builds refs[...] without VarData)."""

import reflex as rx

import reflex_enterprise as rxe

ROWS = [{"make": "Tesla", "price": 1}, {"make": "Ford", "price": 2}, {"make": "Kia", "price": 3}]
COLS = [{"field": "make"}, {"field": "price"}]


def index() -> rx.Component:
    return rx.vstack(
        rxe.ag_grid(id="top", row_data=ROWS, column_defs=COLS, aligned_grids=["bottom"], width="400px", height="200px"),
        rxe.ag_grid(id="bottom", row_data=ROWS, column_defs=COLS, aligned_grids=["top"], width="400px", height="200px"),
    )


app = rxe.App()
app.add_page(index)
