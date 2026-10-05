"""Render-count instrumentation app for reflex 0.9.12a1 cluster render_ctx_statemgr.

Exercises per-substate context providers (#6181) and stable ThemeProvider /
EventLoopProvider context values (#6180) with 10 substates, rx.memo,
rx.ComponentState, rx.foreach, client storage, client_state, background tasks,
multi-page navigation and a dynamic route.
"""

import asyncio
import os

import reflex as rx

# ---- render probe -------------------------------------------------------


class RenderProbe(rx.el.Span):
    """A span whose render bumps window.__renders[<data-probe>]."""

    def add_hooks(self) -> list[str]:
        raw = self.custom_attrs.get("data-probe", "?")
        name = str(raw if isinstance(raw, rx.Var) else rx.Var.create(raw))
        return [
            "if (typeof window !== 'undefined') {"
            "  window.__renders = window.__renders || {};"
            f" window.__renders[{name}] = (window.__renders[{name}] || 0) + 1;"
            "}"
        ]


def probe(name) -> rx.Component:
    return RenderProbe.create(custom_attrs={"data-probe": rx.Var.create(name)})


# ---- states -------------------------------------------------------------


class SubA(rx.State):
    count: int = 0
    rows: list[str] = [f"row-{i}" for i in range(300)]

    @rx.event
    def bump(self):
        self.count += 1

    @rx.event
    async def on_load_both(self):
        """One on_load event that touches two sibling substates."""
        self.count += 1
        sub_b = await self.get_state(SubB)
        sub_b.count += 1

    @rx.event
    def rebuild_rows(self):
        self.rows = [f"row-{i}-{self.count}" for i in range(300)]


class SubB(rx.State):
    count: int = 0
    storm_running: bool = False

    @rx.event(background=True)
    async def storm(self):
        async with self:
            if self.storm_running:
                return
            self.storm_running = True
        for _ in range(50):
            async with self:
                self.count += 1
            await asyncio.sleep(0.1)
        async with self:
            self.storm_running = False

    @rx.event(background=True)
    async def storm_page2(self):
        """Background task started on page 1 that pushes deltas to a page-2-only substate."""
        for _ in range(10):
            async with self:
                page2 = await self.get_state(Page2State)
                page2.count += 1
            await asyncio.sleep(0.1)


class SubC(rx.State):
    count: int = 0

    @rx.event
    def bump(self):
        self.count += 1


class SubD(rx.State):
    count: int = 0


class SubE(rx.State):
    count: int = 0


class SubF(rx.State):
    count: int = 0


class SubG(rx.State):
    count: int = 0


class SubH(rx.State):
    count: int = 0

    @rx.event
    def chain(self):
        """Event chain touching three substates in one round trip."""
        self.count += 1
        yield SubC.bump
        yield SubA.bump


class Store1(rx.State):
    ls: str = rx.LocalStorage("", name="probe_ls")
    ss: str = rx.SessionStorage("", name="probe_ss")

    @rx.event
    def set_ls(self, v: str):
        self.ls = v

    @rx.event
    def set_ss(self, v: str):
        self.ss = v


class Store2(rx.State):
    ck: str = rx.Cookie("", name="probe_ck")

    @rx.event
    def set_ck(self, v: str):
        self.ck = v


class Page2State(rx.State):
    """Only consumed by /page2."""

    count: int = 0

    @rx.event
    def bump(self):
        self.count += 1


class LateState(rx.State):
    """Only mounted behind a rx.cond that starts False."""

    count: int = 0
    shown: bool = False

    @rx.event
    def toggle(self):
        self.shown = not self.shown

    @rx.event
    def bump(self):
        self.count += 1


if os.environ.get("RENDERAPP_EXTRA_STATE"):

    class BackendOnlyState(rx.State):
        """Exists only when the env var is set (stale-frontend repro)."""

        count: int = 0


cs_var = rx._x.client_state(default="", var_name="cstest")

CS_STATES = [SubA, SubB, SubC, SubD, SubE, SubF, SubG, SubH]


# ---- memoized sections --------------------------------------------------


@rx.memo
def sect(name: rx.Var[str], value: rx.Var[int]) -> rx.Component:
    return rx.el.div(
        probe(name),
        rx.el.span(name, style={"font_weight": "bold", "margin_right": "6px"}),
        rx.el.span(value.to_string(), custom_attrs={"data-value": name}),
        style={"display": "inline-block", "margin": "4px", "padding": "2px 6px", "border": "1px solid #888"},
    )


@rx.memo
def dual(a: rx.Var[int], b: rx.Var[int]) -> rx.Component:
    return rx.el.div(
        probe("dual"),
        rx.el.span("dual(A,B)=", style={"font_weight": "bold"}),
        rx.el.span(a.to_string() + "/" + b.to_string(), id="dual-value"),
        style={"margin": "4px"},
    )


@rx.memo
def row_item(label: rx.Var[str]) -> rx.Component:
    return rx.el.li(probe("foreach_row"), label, style={"font_size": "9px", "display": "inline-block", "margin_right": "4px"})


@rx.memo
def color_section(cm_label: rx.Var[str]) -> rx.Component:
    return rx.el.div(
        probe("colormode"),
        rx.color_mode_cond(light=rx.el.span("LIGHT", id="cm-text"), dark=rx.el.span("DARK", id="cm-text")),
        rx.color_mode.button(),
        style={"margin": "4px"},
    )


@rx.memo
def evloop_section(label: rx.Var[str]) -> rx.Component:
    return rx.el.div(
        probe("evloop"),
        rx.el.button(label, on_click=SubA.bump, id="ev-btn"),
        style={"margin": "4px"},
    )


class CounterCS(rx.ComponentState):
    n: int = 0

    @rx.event
    def inc(self):
        self.n += 1

    @classmethod
    def get_component(cls, **props):
        return rx.el.div(
            probe("componentstate"),
            rx.el.span("CS=", style={"font_weight": "bold"}),
            rx.el.span(cls.n.to_string(), id=props.pop("value_id", "cs-value")),
            rx.el.button("cs+", on_click=cls.inc, id=props.pop("btn_id", "cs-btn")),
            **props,
        )


cs_one = CounterCS.create(value_id="cs-value", btn_id="cs-btn")
cs_two = CounterCS.create(value_id="cs2-value", btn_id="cs2-btn")


# ---- pages --------------------------------------------------------------


def index() -> rx.Component:
    return rx.el.div(
        probe("PAGE"),
        rx.el.h2("render_ctx_statemgr probe app"),
        rx.el.div(
            sect(name="A", value=SubA.count),
            sect(name="B", value=SubB.count),
            sect(name="C", value=SubC.count),
            sect(name="D", value=SubD.count),
            sect(name="E", value=SubE.count),
            sect(name="F", value=SubF.count),
            sect(name="G", value=SubG.count),
            sect(name="H", value=SubH.count),
        ),
        dual(a=SubA.count, b=SubB.count),
        color_section(cm_label="x"),
        evloop_section(label="bump A (evloop)"),
        cs_one,
        cs_two,
        rx.el.div(
            rx.el.button("bump A", on_click=SubA.bump, id="a-btn"),
            rx.el.button("bump C", on_click=SubC.bump, id="c-btn"),
            rx.el.button("chain H->C->A", on_click=SubH.chain, id="h-btn"),
            rx.el.button("storm B", on_click=SubB.storm, id="storm-btn"),
            rx.el.button("storm page2", on_click=SubB.storm_page2, id="storm2-btn"),
            rx.el.button("rebuild rows", on_click=SubA.rebuild_rows, id="rows-btn"),
            rx.el.button("toggle late", on_click=LateState.toggle, id="late-toggle"),
        ),
        rx.cond(
            LateState.shown,
            rx.el.div(
                probe("late"),
                rx.el.span("late=", style={"font_weight": "bold"}),
                rx.el.span(LateState.count.to_string(), id="late-value"),
                rx.el.button("bump late", on_click=LateState.bump, id="late-btn"),
            ),
        ),
        rx.el.div(
            rx.el.input(
                value=Store1.ls, on_change=Store1.set_ls, id="ls-input", placeholder="localstorage"
            ),
            rx.el.input(
                value=Store1.ss, on_change=Store1.set_ss, id="ss-input", placeholder="sessionstorage"
            ),
            rx.el.input(
                value=Store2.ck, on_change=Store2.set_ck, id="ck-input", placeholder="cookie"
            ),
            rx.el.input(
                value=cs_var.value, on_change=cs_var.set_value, id="cs-input", placeholder="client_state"
            ),
            rx.el.span(Store1.ls, id="ls-echo"),
            rx.el.span(Store1.ss, id="ss-echo"),
            rx.el.span(Store2.ck, id="ck-echo"),
        ),
        rx.el.ul(rx.foreach(SubA.rows, lambda r: row_item(label=r)), id="rows"),
        rx.el.div(
            rx.link("page2", href="/page2", id="to-page2"),
            " | ",
            rx.link("dyn", href="/d/abc", id="to-dyn"),
        ),
        id="root",
        style={"padding": "10px", "font_family": "monospace"},
    )


def page2() -> rx.Component:
    return rx.el.div(
        probe("PAGE2"),
        rx.el.h2("page2"),
        rx.el.span("page2count=", style={"font_weight": "bold"}),
        rx.el.span(Page2State.count.to_string(), id="p2-value"),
        rx.el.button("bump page2", on_click=Page2State.bump, id="p2-btn"),
        rx.el.div(rx.el.span(SubA.count.to_string(), id="p2-a-value")),
        rx.el.div(rx.link("home", href="/", id="to-home")),
        id="root2",
        style={"padding": "10px", "font_family": "monospace"},
    )


def dyn() -> rx.Component:
    return rx.el.div(
        probe("DYN"),
        rx.el.h2("dyn"),
        rx.el.span(rx.State.pid, id="dyn-pid"),
        rx.el.span(SubA.count.to_string(), id="dyn-a-value"),
        rx.el.div(rx.link("home", href="/", id="to-home")),
        id="root3",
    )


app = rx.App()
app.add_page(index, route="/", on_load=SubA.on_load_both)
app.add_page(page2, route="/page2")
app.add_page(dyn, route="/d/[pid]")
