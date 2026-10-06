"""Plotly title normalization (#7226) and Recharts tick formatters (#7366)."""

import asyncio
import math

import plotly.graph_objects as go
import reflex as rx
from reflex_base.vars.function import ArgsFunctionOperation, FunctionStringVar

from .common import guarded, nav


def _bar() -> go.Figure:
    return go.Figure(data=[go.Bar(x=["a", "b", "c"], y=[1, 3, 2])])


FIG_STR = go.Figure(data=[go.Bar(x=["a", "b"], y=[2, 1])], layout={"title": "Fig string title"})
FIG_OBJ = go.Figure(
    data=[go.Bar(x=["a", "b"], y=[1, 2])],
    layout=go.Layout(title=go.layout.Title(text="Fig object title")),
)
SHARED_LAYOUT = {"title": "Shared title", "height": 220}


class PlotState(rx.State):
    """Plotly state."""

    title: str = "State title 1"
    layout: dict = {"title": "Dict state title 1", "height": 240}
    show: bool = True
    fig: go.Figure = go.Figure(data=[go.Scatter(x=[1, 2, 3], y=[3, 1, 2])], layout={"title": "State fig title 1"})

    @rx.event
    def bump(self):
        self.title = "State title 2"
        self.layout = {"title": "Dict state title 2", "height": 240}
        self.fig = go.Figure(data=[go.Scatter(x=[1, 2, 3], y=[1, 2, 3])], layout={"title": "State fig title 2"})

    @rx.event
    def toggle(self):
        self.show = not self.show


def _plot(pid: str, **kw) -> rx.Component:
    return rx.box(rx.plotly(id=pid, height="230px", width="360px", **kw), width="380px", height="250px")


def plotly_page() -> rx.Component:
    """Plotly page."""
    return rx.vstack(
        nav(),
        rx.heading("Plotly titles"),
        rx.hstack(
            rx.button("bump", on_click=PlotState.bump, id="plot-bump"),
            rx.button("toggle", on_click=PlotState.toggle, id="plot-toggle"),
        ),
        rx.flex(
            _plot("p_str", data=_bar(), layout={"title": "Literal string title", "height": 230}),
            _plot("p_obj", data=_bar(), layout={"title": {"text": "Literal object title", "font": {"color": "red"}}, "height": 230}),
            _plot("p_state_str", data=_bar(), layout={"title": PlotState.title, "height": 230}),
            _plot("p_state_dict", data=_bar(), layout=PlotState.layout),
            rx.cond(PlotState.show, _plot("p_cond", data=_bar(), layout={"title": "Cond title"})),
            _plot("p_shared1", data=_bar(), layout=SHARED_LAYOUT),
            _plot("p_shared2", data=_bar(), layout=SHARED_LAYOUT),
            _plot("p_fig_str", data=FIG_STR),
            _plot("p_fig_obj", data=FIG_OBJ),
            _plot("p_fig_override", data=FIG_STR, layout={"title": "Override title"}),
            _plot("p_state_fig", data=PlotState.fig),
            wrap="wrap",
        ),
        padding="10px",
    )


def _series(t: int) -> list[dict]:
    return [{"x": i, "y": round(50 + 40 * math.sin((i + t) / 2), 2)} for i in range(10)]


class ChartState(rx.State):
    """Recharts state; background task updates data every 500ms."""

    currency: str = "$"
    data: list[dict] = _series(0)
    ticks: int = 0
    running: bool = False

    @rx.event
    def toggle_currency(self):
        self.currency = "EUR " if self.currency == "$" else "$"

    @rx.event(background=True)
    async def run(self):
        async with self:
            if self.running:
                return
            self.running = True
        for _ in range(20):
            await asyncio.sleep(0.5)
            async with self:
                self.ticks += 1
                self.data = _series(self.ticks)
        async with self:
            self.running = False


F_VAR_CREATE = rx.Var.create("(v) => 'A' + v")
F_FUNCSTR = FunctionStringVar.create("((v) => v + 'u')")
F_PARTIAL = FunctionStringVar.create("((c, v) => c + v)").partial(ChartState.currency)
F_ARGS = ArgsFunctionOperation.create(("v",), ChartState.currency + rx.Var("v").to(str))


def _chart(cid: str, x_fmt, y_fmt=None) -> rx.Component:
    return rx.box(
        rx.recharts.line_chart(
            rx.recharts.line(data_key="y", is_animation_active=False),
            rx.recharts.x_axis(data_key="x", tick_formatter=x_fmt),
            rx.recharts.y_axis(**({"tick_formatter": y_fmt} if y_fmt is not None else {})),
            data=ChartState.data,
            width=380,
            height=200,
        ),
        id=cid,
        width="400px",
    )


MEMO_CHART_ERR = ""
try:

    @rx.memo
    def memo_chart(data: rx.Var[list[dict]], prefix: rx.Var[str]) -> rx.Component:
        """A chart inside rx.memo with a formatter built from a memo prop."""
        fmt = ArgsFunctionOperation.create(("v",), prefix + rx.Var("v").to(str))
        return rx.recharts.line_chart(
            rx.recharts.line(data_key="y", is_animation_active=False),
            rx.recharts.x_axis(data_key="x", tick_formatter=fmt),
            data=data,
            width=380,
            height=200,
        )

except Exception as _e:  # noqa: BLE001
    MEMO_CHART_ERR = f"{type(_e).__name__}: {_e}"
    print("CONSTRUCTION_ERROR memo_chart definition:", MEMO_CHART_ERR, flush=True)
    memo_chart = None


def _memo_chart_box() -> rx.Component:
    if memo_chart is None:
        raise RuntimeError(f"memo definition failed: {MEMO_CHART_ERR}")
    return rx.box(memo_chart(data=ChartState.data, prefix=ChartState.currency), id="rc_memo")


def recharts_page() -> rx.Component:
    """Recharts page."""
    return rx.vstack(
        nav(),
        rx.heading("Recharts tick formatters"),
        rx.hstack(
            rx.button("currency", on_click=ChartState.toggle_currency, id="rc-currency"),
            rx.button("run 10s", on_click=ChartState.run, id="rc-run"),
            rx.text("ticks:", ChartState.ticks, id="rc-ticks"),
            rx.text("running:", ChartState.running.to_string(), id="rc-running"),
            rx.text("currency:", ChartState.currency, id="rc-cur"),
        ),
        rx.flex(
            guarded("rc_literal", lambda: _chart("rc_literal", "(v) => 'L' + v")),
            guarded("rc_var_create", lambda: _chart("rc_var_create", F_VAR_CREATE)),
            guarded("rc_funcstr", lambda: _chart("rc_funcstr", F_FUNCSTR)),
            guarded("rc_partial", lambda: _chart("rc_partial", F_PARTIAL, F_PARTIAL)),
            guarded("rc_args", lambda: _chart("rc_args", F_ARGS)),
            guarded("rc_untyped", lambda: _chart("rc_untyped", rx.Var("(v) => 'R' + v"))),
            guarded("rc_memo", _memo_chart_box),
            wrap="wrap",
        ),
        padding="10px",
    )
