"""R101-01 re-check: editable AG Grids + memoized consumers of the SAME state list (+ optional recharts, R101-22)."""
import json
import os
from typing import Any

import reflex as rx
import reflex_enterprise as rxe

assert f"/envs/{os.environ.get('EXPECT_VENV', 'ent910')}/" in rx.__file__, rx.__file__
CHART = os.environ.get("GF_CHART") == "1"
START = [{"uid": f"u-{i}", "price": p, "addr": {"city": c}} for i, (p, c) in enumerate([(40, "oslo"), (10, "rome"), (50, "lima")], 1)]


def _apply(rows, params, fn):
    uid = params.get("node_id")
    for r in rows:
        if r["uid"] == uid:
            fn(r, params)
    return uid


class GS(rx.State):
    rows: list[dict[str, Any]] = [json.loads(json.dumps(r)) for r in START]
    log: list[str] = []
    cols: list[dict[str, Any]] = [{"field": "uid"}, {"field": "price", "editable": True}, {"field": "addr.city", "editable": True}]

    def _edit(self, r, p):
        if p["field"] == "price":
            r["price"] = int(p["newValue"])
        else:
            r["addr"]["city"] = p["newValue"]

    @rx.event
    def on_edit(self, params: dict[str, Any]):
        uid = _apply(self.rows, params, self._edit)
        self.log.append(f"edit:{uid}={params.get('newValue')}")

    @rx.event
    def clamp_edit(self, params: dict[str, Any]):
        uid = _apply(self.rows, params, lambda r, p: r.__setitem__("price", min(int(p["newValue"]), 100)))
        self.log.append(f"clamp:{uid}={params.get('newValue')}")

    @rx.event
    def reject_edit(self, params: dict[str, Any]):
        self.log.append(f"reject:{params.get('node_id')}={params.get('newValue')}")

    @rx.event
    def reset_rows(self):
        self.rows = [json.loads(json.dumps(r)) for r in START]
        self.log = []

    @rx.var
    def rows_json(self) -> str:
        return json.dumps(self.rows)


@rx.memo
def memo_view(rows: rx.Var[list[dict[str, Any]]]) -> rx.Component:
    return rx.text(rows.to_string(), id="memo")


def grid(gid, handler):
    return rxe.ag_grid(id=gid, row_id_key="uid", column_defs=GS.cols, row_data=GS.rows, on_cell_value_changed=handler, width="500px", height="180px")


def index():
    return rx.vstack(
        rx.button("reset", id="reset", on_click=GS.reset_rows),
        rx.text(GS.rows_json, id="json"),
        rx.text(GS.log.join(","), id="log"),
        rx.text(GS.rows.to_string(), id="raw"),
        memo_view(rows=GS.rows),
        grid("ga", GS.on_edit),
        grid("gc", GS.clamp_edit),
        grid("gr", GS.reject_edit),
        rxe.ag_grid(id="gb", column_defs=GS.cols, row_data=GS.rows, width="500px", height="180px"),
        rx.recharts.bar_chart(rx.recharts.bar(data_key="price", is_animation_active=False), rx.recharts.x_axis(data_key="uid"), data=GS.rows, width=300, height=150) if CHART else rx.fragment(),
        rx.foreach(GS.rows, lambda r: rx.text(r["uid"], ":", r["price"], ":", r["addr"].to(dict)["city"], class_name="fe-row")),
    )


app = rxe.App()
app.add_page(index, route="/")
