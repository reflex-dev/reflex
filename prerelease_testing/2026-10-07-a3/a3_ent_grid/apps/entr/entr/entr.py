"""a3_ent_grid regression-hunt fixture for enterprise#273 (formatColumnDefs no longer waits for window.__reflex).

Every grid sits on a prerendered (static) route. Literal column defs go through enterprise's Python ColumnDef path;
Var-valued ones (State var, State default holding Python lambdas, computed var, rx.cond, @rx.memo prop) go through
the JS `formatColumnDefs` at render time, which since 0.9.7a5 runs on the FIRST render, before reflex assigns
`window.__reflex` in its ReflexProviders useEffect. Trace renderers push {ev, t, has} into window.__trace so the
driver can order the first cell render against the `window.__reflex` assignment.
"""

from typing import Any

import reflex as rx
import reflex_enterprise as rxe
from reflex.components import dynamic

ROWS = [
    {"make": "Tesla", "price": 1, "country": "US"},
    {"make": "Ford", "price": 2, "country": "US"},
    {"make": "Toyota", "price": 3, "country": "JP"},
]
PINNED = [{"make": "PINNED", "price": 99, "country": "XX"}]

# Python lambdas built OUTSIDE a ColumnDef (rx.cond branches) are converted when the page is evaluated, before the
# compiler has bundled Radix; the enterprise error message asks for this registration.
dynamic.bundle_library("@radix-ui/themes")

# Python-side trace renderer: records whether window.__reflex exists when AG Grid invokes the renderer.
TRACE_LIT = rx.vars.function.ArgsFunctionOperation.create(
    args_names=["params"],
    return_expr=rx.Var(
        "((window.__trace = window.__trace || []).push({ev: 'cell_render', src: 'literal', t: performance.now(), "
        "has: typeof window.__reflex !== 'undefined'}), 'T:' + String(params.value))"
    ),
)
# JS-string trace renderer for State-held column defs (formatColumnDefs evals arrow-function strings).
TRACE_JS = (
    "(params) => { (window.__trace = window.__trace || []).push({ev: 'cell_render', src: 'state_js', "
    "t: performance.now(), has: typeof window.__reflex !== 'undefined'}); return 'S:' + String(params.value); }"
)


@rx.memo
def cell_memo(value: rx.Var[str]) -> rx.Component:
    """A memo component used from a lambda cell renderer (the demo's documented pattern)."""
    return rx.badge("memo:", value, color_scheme="purple", class_name="memo-badge")


def lambda_cols(prefix: str) -> list[dict[str, Any]]:
    """Column defs mixing Python lambdas (components/formatters/getters) with string expressions."""
    return [
        {
            "field": "make",
            "header_name": f"{prefix}make",
            "cell_renderer": lambda params: rx.badge(params.value, color_scheme="green"),
            "tooltip_field": "make",
            "header_tooltip": "make tooltip",
        },
        {
            "field": "price",
            "header_name": f"{prefix}price",
            "value_formatter": lambda params: "$" + params.value.to_string(),
            "cell_class_rules": {"cheap": "x < 2"},
        },
        {
            "field": "double",
            "header_name": f"{prefix}double",
            "value_getter": lambda params: params.data.price.to(int) * 2,
        },
        {
            "field": "tip",
            "header_name": f"{prefix}tip",
            "value_getter": "params.data.country",
            "cell_renderer": lambda params: rx.tooltip(rx.text(params.value, class_name="tip-text"), content="tooltip"),
        },
        {
            "field": "memo",
            "header_name": f"{prefix}memo",
            "value_getter": "params.data.make",
            "cell_renderer": lambda params: cell_memo(value=params.value),
        },
        {"field": "trace", "header_name": f"{prefix}trace", "value_getter": "params.data.make", "cell_renderer": TRACE_LIT},
    ]


LIT_COLS = lambda_cols("L:")


class VState(rx.State):
    """Var-valued column defs; nothing modifies these during boot."""

    rows: list[dict[str, Any]] = ROWS
    pinned: list[dict[str, Any]] = PINNED
    flag: bool = True
    clicks: int = 0
    js_cols: list[dict[str, Any]] = [
        {"field": "make", "header_name": "J:make", "cell_renderer": TRACE_JS, "tooltip_field": "country"},
        {"field": "price", "header_name": "J:price", "value_formatter": "'$' + params.value", "cell_class_rules": {"cheap": "x < 2"}},
        {"field": "double", "header_name": "J:double", "value_getter": {"function": "params.data.price * 2"}},
        {"field": "arrow", "header_name": "J:arrow", "value_getter": "(params) => params.data.make.toUpperCase()"},
    ]
    group_cols: list[dict[str, Any]] = [
        {"field": "country", "row_group": True, "hide": True},
        {"field": "make", "header_name": "G:make"},
        {"field": "price", "header_name": "G:price", "agg_func": "sum"},
    ]
    lam_cols: list[dict[str, Any]] = lambda_cols("S:")

    @rx.var
    def computed_cols(self) -> list[dict[str, Any]]:
        return [{"field": "make", "header_name": "C:make"}, {"field": "price", "header_name": "C:price", "value_formatter": "params.value + ' EUR'"}]

    @rx.event
    def bump(self):
        self.clicks += 1

    @rx.event
    def toggle(self):
        self.flag = not self.flag


class DState(rx.State):
    """Master/detail params held in State (JS-string renderer in the detail grid)."""

    rows: list[dict[str, Any]] = [
        {"id": 1, "name": "A", "counts": [{"count": 10, "value": "x"}, {"count": 5, "value": "y"}]},
        {"id": 2, "name": "B", "counts": [{"count": 50, "value": "z"}]},
    ]
    params: dict[str, Any] = {
        "detail_grid_options": {
            "column_defs": [{"field": "count", "cell_renderer": TRACE_JS}, {"field": "value", "value_formatter": "'v=' + params.value"}],
        },
        "get_detail_row_data": "(params) => params.successCallback(params.data.counts)",
    }


DETAIL_OUTER = [{"field": "id", "cell_renderer": "agGroupCellRenderer"}, {"field": "name"}]


def grid(wrap_id: str, **props) -> rx.Component:
    props.setdefault("width", "900px")
    props.setdefault("height", "200px")
    return rx.box(rxe.ag_grid(id=wrap_id + "_grid", **props), id=wrap_id)


@rx.memo
def memo_grid(cols: rx.Var[list[dict[str, Any]]], rows: rx.Var[list[dict[str, Any]]]) -> rx.Component:
    return rxe.ag_grid(id="memo_lam_grid", column_defs=cols, row_data=rows, width="900px", height="200px")


def nav() -> rx.Component:
    return rx.hstack(
        *[rx.link(n, href=h, id=f"nav-{n}") for n, h in [("lit", "/lit"), ("var", "/var"), ("detail", "/detail2"), ("memo", "/memo2"), ("other", "/other")]]
    )


def lit_page() -> rx.Component:
    dynamic.bundle_library(cell_memo(value=""))
    return rx.vstack(
        nav(),
        rx.heading("entr lit", id="heading"),
        rx.box(cell_memo(value=""), display="none"),
        rx.text("literal column defs with python lambdas (+ pinned top row):"),
        grid("w_lit", column_defs=LIT_COLS, row_data=ROWS, pinned_top_row_data=PINNED, tooltip_show_delay=0),
        rx.text("literal row grouping:"),
        grid("w_lit_group", column_defs=[{"field": "country", "row_group": True, "hide": True}, {"field": "make"}, {"field": "price", "agg_func": "sum"}],
             row_data=ROWS, group_default_expanded=-1),
    )


def var_page() -> rx.Component:
    dynamic.bundle_library(cell_memo(value=""))
    return rx.vstack(
        nav(),
        rx.heading("entr var", id="heading"),
        rx.box(cell_memo(value=""), display="none"),
        rx.text("clicks: ", VState.clicks, " flag: ", VState.flag.to_string(), id="counters"),
        rx.button("bump", on_click=VState.bump, id="bump"),
        rx.button("toggle", on_click=VState.toggle, id="toggle"),
        rx.text("State var with JS-string expressions (trace renderer, formatter, {function} getter, arrow getter):"),
        grid("w_js", column_defs=VState.js_cols, row_data=VState.rows, pinned_top_row_data=VState.pinned),
        rx.text("State var whose default holds python lambdas:"),
        grid("w_lam", column_defs=VState.lam_cols, row_data=VState.rows),
        rx.text("rx.cond Var whose branches are literal lists with python lambdas:"),
        grid("w_cond", column_defs=rx.cond(VState.flag, LIT_COLS, [{"field": "make", "header_name": "plain"}]), row_data=VState.rows),
        rx.text("computed var column defs:"),
        grid("w_comp", column_defs=VState.computed_cols, row_data=VState.rows),
        rx.text("State var column defs with row grouping:"),
        grid("w_group", column_defs=VState.group_cols, row_data=VState.rows, group_default_expanded=-1),
    )


def detail_page() -> rx.Component:
    dynamic.bundle_library(cell_memo(value=""))
    return rx.vstack(
        nav(),
        rx.heading("entr detail", id="heading"),
        rx.text("master/detail, literal detail params, python-lambda renderers in the detail grid:"),
        grid(
            "w_dlit",
            column_defs=DETAIL_OUTER,
            row_data=DState.rows,
            master_detail=True,
            detail_cell_renderer_params={
                "detail_grid_options": {
                    "column_defs": [
                        {"field": "count", "cell_renderer": lambda params: rx.badge(params.value, color_scheme="red")},
                        {"field": "value", "cell_renderer": TRACE_LIT},
                    ]
                },
                "get_detail_row_data": lambda params: rx.vars.function.FunctionStringVar("params.successCallback").call(params.data.counts),
            },
        ),
        rx.text("master/detail, State detail params (JS-string renderer + formatter):"),
        grid("w_dstate", column_defs=DETAIL_OUTER, row_data=DState.rows, master_detail=True, detail_cell_renderer_params=DState.params),
    )


def memo_page() -> rx.Component:
    dynamic.bundle_library(cell_memo(value=""))
    return rx.vstack(
        nav(),
        rx.heading("entr memo", id="heading"),
        rx.box(cell_memo(value=""), display="none"),
        rx.text("@rx.memo grid, column_defs prop = State var holding python lambdas:"),
        rx.box(memo_grid(cols=VState.lam_cols, rows=VState.rows), id="w_memo_lam"),
    )


def other() -> rx.Component:
    return rx.vstack(nav(), rx.heading("entr other", id="heading"))


app = rxe.App()
app.add_page(lit_page, route="/lit")
app.add_page(var_page, route="/var")
app.add_page(detail_page, route="/detail2")
app.add_page(memo_page, route="/memo2")
app.add_page(other, route="/other")
app.add_page(other, route="/")
