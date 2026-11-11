"""Minimal enterprise repro: AG Grid whose column_defs come from a State var renders no columns on a full prod page load."""

import reflex as rx

import reflex_enterprise as rxe


class GridState(rx.State):
    rows: list[dict] = [{"make": "Tesla", "price": 1}, {"make": "Ford", "price": 2}]
    cols: list[dict] = [{"field": "make", "header_name": "Make"}, {"field": "price", "header_name": "Price"}]


def index():
    return rx.vstack(
        rx.heading("State column_defs"),
        rxe.ag_grid(id="state_cols", column_defs=GridState.cols, row_data=GridState.rows, width="400px", height="200px"),
        rx.heading("Literal column_defs"),
        rxe.ag_grid(
            id="literal_cols",
            column_defs=[{"field": "make", "header_name": "Make"}, {"field": "price", "header_name": "Price"}],
            row_data=GridState.rows,
            width="400px",
            height="200px",
        ),
    )


app = rxe.App()
app.add_page(index)
