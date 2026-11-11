"""AG Grid API repro: select all via the grid API, read selected rows back into State."""

import reflex as rx

import reflex_enterprise as rxe
from reflex_enterprise.components.ag_grid.aggrid import AgGridAPI

ROWS = [{"make": "Tesla", "price": 1}, {"make": "Ford", "price": 2}, {"make": "Kia", "price": 3}]


class S(rx.State):
    selected: int = -1

    @rx.event
    def got_rows(self, rows: list[dict]):
        self.selected = len(rows)


def index() -> rx.Component:
    grid = rxe.ag_grid(
        id="grid1",
        row_data=ROWS,
        column_defs=[{"field": "make"}, {"field": "price"}],
        row_selection={"mode": "multiRow"},
        width="400px",
        height="300px",
    )
    api = AgGridAPI.create("grid1")
    return rx.vstack(
        grid,
        rx.button("select all", id="select-all", on_click=grid.api.select_all()),
        rx.button("select all (AgGridAPI.create)", id="select-all-2", on_click=api.select_all()),
        rx.button("read selection", id="read", on_click=grid.api.getSelectedRows(callback=S.got_rows)),
        rx.text(S.selected, id="selected"),
    )


app = rxe.App()
app.add_page(index)
