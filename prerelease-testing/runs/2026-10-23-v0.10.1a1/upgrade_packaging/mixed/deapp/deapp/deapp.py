"""data_editor isolation app (#7607 / #7273): every column typed so 0.10.0 renders too.

/        : state-backed columns + data; `add_row_append` mutates the list in place, `add_row_assign` reassigns a new list;
           `more_cols` appends a column in place. A literal-columns editor sits next to it.
Driver: hover/click the grid after each mutation and count page errors (glide `Cannot read properties of undefined (reading '0')`).
"""

import json
import os

import reflex as rx

_qa_ev = os.environ.get("QA_EXPECT_VENV")
if _qa_ev:  # QA venv guard
    assert f"/envs/{_qa_ev}/" in rx.__file__, rx.__file__


class State(rx.State):
    columns: list[dict] = [
        {"title": "Name", "type": "str", "id": "name"},
        {"title": "Age", "type": "int", "id": "age"},
    ]
    data: list[list] = [["ada", 36], ["grace", 45], ["linus", 55]]
    cell: str = ""
    log: list[str] = []

    @rx.event
    def add_row_append(self):
        self.data.append([f"new{len(self.data)}", len(self.data)])

    @rx.event
    def add_row_assign(self):
        self.data = [*self.data, [f"new{len(self.data)}", len(self.data)]]

    @rx.event
    def more_cols(self):
        self.columns.append({"title": f"C{len(self.columns)}", "type": "str", "id": f"c{len(self.columns)}"})
        self.data = [[*row, "x"] for row in self.data]

    @rx.event
    def cell_clicked(self, pos):
        self.cell = json.dumps(pos)
        self.log.append(json.dumps(pos))

    @rx.event
    def reset(self):
        self.data = [["ada", 36], ["grace", 45], ["linus", 55]]
        self.columns = [
            {"title": "Name", "type": "str", "id": "name"},
            {"title": "Age", "type": "int", "id": "age"},
        ]


def index():
    return rx.vstack(
        rx.heading("data_editor isolation", id="title"),
        rx.box(
            rx.data_editor(columns=State.columns, data=State.data, on_cell_clicked=State.cell_clicked, height="220px"),
            id="de_state",
        ),
        rx.hstack(
            rx.button("append", on_click=State.add_row_append, id="append"),
            rx.button("assign", on_click=State.add_row_assign, id="assign"),
            rx.button("more_cols", on_click=State.more_cols, id="more_cols"),
            rx.button("reset", on_click=State.reset, id="reset"),
        ),
        rx.text(State.data.length(), id="nrows"),
        rx.text(State.columns.length(), id="ncols"),
        rx.text(State.cell, id="cell"),
        rx.box(
            rx.data_editor(columns=[{"title": "Lit", "type": "str", "id": "lit"}, {"title": "N", "type": "int", "id": "n"}], data=[["x", 1], ["y", 2]], height="120px"),
            id="de_literal",
        ),
        spacing="3",
        padding="1em",
    )


app = rx.App()
app.add_page(index, route="/")
