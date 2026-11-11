"""EN-1 minimal: an editable AG Grid plus memoized consumers (recharts, rx.memo) of the SAME state list."""
import json
import os
from typing import Any

import reflex as rx
import reflex_enterprise as rxe

assert f"/envs/{os.environ.get('EXPECT_VENV', 'new-ent')}/" in rx.__file__, rx.__file__

START = [{"uid": f"u-{i}", "price": p} for i, p in enumerate([40, 10, 50], 1)]


class GS(rx.State):
    rows: list[dict[str, Any]] = [dict(r) for r in START]
    log: list[str] = []
    cols: list[dict[str, Any]] = [{"field": "uid"}, {"field": "price", "editable": True}]

    @rx.event
    def on_edit(self, params: dict[str, Any]):
        uid = params.get("node_id")
        for r in self.rows:
            if r["uid"] == uid:
                r["price"] = int(params["newValue"])
        self.log.append(f"edit:{uid}={params.get('newValue')}")

    @rx.event
    def clamp_edit(self, params: dict[str, Any]):
        # server-side validation: clamp to 100
        uid = params.get("node_id")
        for r in self.rows:
            if r["uid"] == uid:
                r["price"] = min(int(params["newValue"]), 100)
        self.log.append(f"clamp:{uid}={params.get('newValue')}")

    @rx.event
    def reset_rows(self):
        self.rows = [dict(r) for r in START]
        self.log = []

    @rx.var
    def rows_json(self) -> str:
        return json.dumps(self.rows)


@rx.memo
def memo_view(rows: rx.Var[list[dict[str, Any]]]) -> rx.Component:
    return rx.text(rows.to_string(), id="memo")


def index():
    return rx.vstack(
        rx.button("reset", id="reset", on_click=GS.reset_rows),
        rx.text(GS.rows_json, id="json"),
        rx.text(GS.log.join(","), id="log"),
        rx.text(GS.rows.to_string(), id="raw"),
        memo_view(rows=GS.rows),
        rxe.ag_grid(id="ga", row_id_key="uid", column_defs=GS.cols, row_data=GS.rows, on_cell_value_changed=GS.on_edit, width="400px", height="200px"),
        rxe.ag_grid(id="gc", row_id_key="uid", column_defs=GS.cols, row_data=GS.rows, on_cell_value_changed=GS.clamp_edit, width="400px", height="200px"),
        rx.foreach(GS.rows, lambda r: rx.text(r["uid"], ":", r["price"], class_name="fe-row")),
    )


app = rxe.App()
app.add_page(index, route="/")
