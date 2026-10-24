"""#7273 structural sharing / #7441 shared store with AG Grid: state row_data mutated IN PLACE must reach the grid.

Grid A uses row_id_key="uid" (stable ids), grid B index ids. Every op mutates self.rows in place (nested dict edit,
in-place sort/reverse, append/pop, per-row rename, cell edit from the grid). #json shows the backend list.
"""
import json
from typing import Any

import reflex as rx
import reflex_enterprise as rxe

START = [{"uid": f"u-{i}", "name": n, "price": p} for i, (n, p) in enumerate([("delta", 40), ("alpha", 10), ("echo", 50), ("charlie", 30), ("bravo", 20)], 1)]


class GS(rx.State):
    rows: list[dict[str, Any]] = [dict(r) for r in START]
    log: list[str] = []
    cols: list[dict[str, Any]] = [{"field": "uid"}, {"field": "name"}, {"field": "price", "editable": True}]

    @rx.event
    def bump_first(self):
        self.rows[0]["price"] += 1
        self.log.append("bump_first")

    @rx.event
    def sort_price(self):
        self.rows.sort(key=lambda r: r["price"])
        self.log.append("sort_price")

    @rx.event
    def reverse(self):
        self.rows.reverse()
        self.log.append("reverse")

    @rx.event
    def add_row(self):
        n = len(self.rows) + 1
        self.rows.append({"uid": f"u-{n}", "name": f"new{n}", "price": n * 100})
        self.log.append("add_row")

    @rx.event
    def remove_first(self):
        self.rows.pop(0)
        self.log.append("remove_first")

    @rx.event
    def rename_all(self):
        for r in self.rows:
            r["name"] = r["name"].upper()
        self.log.append("rename_all")

    @rx.event
    def swap_cols(self):
        self.cols[1], self.cols[2] = self.cols[2], self.cols[1]
        self.log.append("swap_cols")

    @rx.event
    def reset(self):
        self.rows = [dict(r) for r in START]
        self.cols = [{"field": "uid"}, {"field": "name"}, {"field": "price", "editable": True}]
        self.log = []

    @rx.event
    def on_edit(self, params: dict[str, Any]):
        uid = params.get("node_id")
        for r in self.rows:
            if r["uid"] == uid or (uid is not None and uid.isdigit() and self.rows.index(r) == int(uid)):
                r[params["field"]] = int(params["newValue"]) if params["field"] == "price" else params["newValue"]
        self.log.append(f"edit:{uid}:{params.get('field')}={params.get('newValue')}")

    @rx.var
    def rows_json(self) -> str:
        return json.dumps(self.rows)

    @rx.var
    def total(self) -> int:
        return sum(int(r["price"]) for r in self.rows)


def index():
    return rx.vstack(
        rx.hstack(
            *[rx.button(n, id=n, on_click=getattr(GS, n)) for n in ("bump_first", "sort_price", "reverse", "add_row", "remove_first", "rename_all", "swap_cols", "reset")],
        ),
        rx.text("total=", GS.total, id="total"),
        rx.text(GS.rows_json, id="json"),
        rx.text(GS.log.join(","), id="log"),
        rxe.ag_grid(id="ga", row_id_key="uid", column_defs=GS.cols, row_data=GS.rows, on_cell_value_changed=GS.on_edit, width="600px", height="300px"),
        rxe.ag_grid(id="gb", column_defs=GS.cols, row_data=GS.rows, on_cell_value_changed=GS.on_edit, width="600px", height="300px"),
        rx.foreach(GS.rows, lambda r: rx.text(r["uid"], ":", r["name"], ":", r["price"], class_name="fe-row")),
    )


app = rxe.App()
app.add_page(index, route="/")
