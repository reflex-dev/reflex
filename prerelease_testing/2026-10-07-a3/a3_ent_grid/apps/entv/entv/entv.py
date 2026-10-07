"""Enterprise fixture: AG Grid whose column_defs come from a State var vs literal column_defs."""

from typing import Any

import reflex as rx
import reflex_enterprise as rxe

from .probe import reflex_probe

LITERAL_COLS = [{"field": "make"}, {"field": "price"}]
ROWS = [
    {"make": "Tesla", "price": 1},
    {"make": "Ford", "price": 2},
    {"make": "Toyota", "price": 3},
]


class GridState(rx.State):
    """Holds the grid config; nothing modifies it during boot."""

    cols: list[dict[str, str]] = LITERAL_COLS
    rows: list[dict[str, Any]] = ROWS
    clicks: int = 0

    @rx.event
    def bump(self):
        self.clicks += 1


class OtherState(rx.State):
    """Unrelated substate."""

    x: int = 0

    @rx.event
    def bump(self):
        self.x += 1


class LoadState(rx.State):
    """Grid config modified by on_load (control: a changed substate)."""

    cols: list[dict[str, str]] = [{"field": "make"}]
    rows: list[dict[str, Any]] = ROWS

    @rx.event
    def on_load_set(self):
        self.cols = [{"field": "make"}, {"field": "price"}]


DETAIL_ROWS = [
    {"id": 1, "name": "A", "counts": [{"count": 10, "value": "x"}, {"count": 5, "value": "y"}]},
    {"id": 2, "name": "B", "counts": [{"count": 50, "value": "z"}]},
]
DETAIL_OUTER_COLS = [
    {"field": "id", "cell_renderer": "agGroupCellRenderer"},
    {"field": "name"},
]
DETAIL_PARAMS = {
    "detail_grid_options": {"column_defs": [{"field": "count"}, {"field": "value"}]},
    "get_detail_row_data": "(params) => params.successCallback(params.data.counts)",
}


class DetailState(rx.State):
    """Detail-grid params held in State (nothing modifies them during boot)."""

    rows: list[dict[str, Any]] = DETAIL_ROWS
    params: dict[str, Any] = DETAIL_PARAMS


def grid(wrap_id: str, **props) -> rx.Component:
    return rx.box(
        rxe.ag_grid(id=wrap_id + "_grid", width="420px", height="180px", **props),
        id=wrap_id,
    )


@rx.memo
def memo_grid_props(cols: rx.Var[list[dict[str, str]]], rows: rx.Var[list[dict[str, Any]]]) -> rx.Component:
    return rxe.ag_grid(id="memo_props_grid", column_defs=cols, row_data=rows, width="420px", height="180px")


@rx.memo
def memo_grid_state() -> rx.Component:
    return rxe.ag_grid(
        id="memo_state_grid",
        column_defs=GridState.cols,
        row_data=GridState.rows,
        width="420px",
        height="180px",
    )


def nav() -> rx.Component:
    return rx.hstack(
        rx.link("index", href="/", id="nav-index"),
        rx.link("other", href="/other", id="nav-other"),
        rx.link("memo", href="/memo", id="nav-memo"),
        rx.link("onload", href="/onload", id="nav-onload"),
    )


def index() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.heading("entv index", id="heading"),
        rx.text("clicks: ", GridState.clicks, " other: ", OtherState.x, id="counters"),
        rx.button("bump other", on_click=OtherState.bump, id="bump-other"),
        rx.button("bump gridstate", on_click=GridState.bump, id="bump-gridstate"),
        reflex_probe(label="gridstate_cols", value=GridState.cols),
        reflex_probe(label="literal", value="lit"),
        rx.text("state-var column_defs:"),
        grid("w_state", column_defs=GridState.cols, row_data=GridState.rows),
        rx.text("literal column_defs:"),
        grid("w_literal", column_defs=LITERAL_COLS, row_data=GridState.rows),
    )


def other() -> rx.Component:
    return rx.vstack(nav(), rx.heading("entv other", id="heading"))


def memo_page() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.heading("entv memo", id="heading"),
        rx.text("rx.memo grid, column_defs passed as prop:"),
        rx.box(memo_grid_props(cols=GridState.cols, rows=GridState.rows), id="w_memo_props"),
        rx.text("rx.memo grid, column_defs read from State inside the memo:"),
        rx.box(memo_grid_state(), id="w_memo_state"),
    )


def onload_page() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.heading("entv onload", id="heading"),
        rx.text("grid whose State var is changed by on_load:"),
        grid("w_onload", column_defs=LoadState.cols, row_data=LoadState.rows),
        rx.text("grid on unchanged GridState on the same page:"),
        grid("w_state2", column_defs=GridState.cols, row_data=GridState.rows),
    )


def detail_page() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.heading("entv detail", id="heading"),
        rx.text("master-detail, LITERAL outer column_defs, detail_cell_renderer_params from State:"),
        grid(
            "w_detail_state",
            column_defs=DETAIL_OUTER_COLS,
            row_data=DetailState.rows,
            master_detail=True,
            detail_cell_renderer_params=DetailState.params,
        ),
        rx.text("master-detail, literal outer column_defs, literal detail params:"),
        grid(
            "w_detail_literal",
            column_defs=DETAIL_OUTER_COLS,
            row_data=DetailState.rows,
            master_detail=True,
            detail_cell_renderer_params={
                "detail_grid_options": {"column_defs": [{"field": "count"}, {"field": "value"}]},
                "get_detail_row_data": lambda params: rx.vars.function.FunctionStringVar(
                    "params.successCallback"
                ).call(params.data.counts),
            },
        ),
    )


def renderer_page() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.heading("entv renderer", id="heading"),
        rx.text("literal column_defs with a Python-lambda cell_renderer returning rx.badge:"),
        grid(
            "w_renderer",
            column_defs=[
                {"field": "make", "cell_renderer": lambda params: rx.badge(params.value)},
                {"field": "price"},
            ],
            row_data=ROWS,
        ),
    )


def item_page() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.heading("entv item", id="heading"),
        rx.text("dynamic route (not prerendered), state-var column_defs:"),
        grid("w_state", column_defs=GridState.cols, row_data=GridState.rows),
        reflex_probe(label="gridstate_cols", value=GridState.cols),
    )


app = rxe.App()
app.add_page(index, route="/")
app.add_page(other, route="/other")
app.add_page(memo_page, route="/memo")
app.add_page(onload_page, route="/onload", on_load=LoadState.on_load_set)
app.add_page(detail_page, route="/detail")
app.add_page(renderer_page, route="/renderer")
app.add_page(item_page, route="/item/[pid]")
