"""Minimal verifier app: is a background-task on_load cancelled by navigation?

Pages:
- /slowbg : on_load is @rx.event(background=True) writing 5 log entries ~1s apart
- /other  : plain target page; has a button that starts the SAME kind of
            background task (for the button-vs-on_load contrast)
"""

import asyncio
import time

import plotly.graph_objects as go

import reflex as rx
from reflex.components.dynamic import bundle_library

# FINDING-017: user-level bundle_library at module import time.
bundle_library("lucide-react")

T0 = time.time()


def ts() -> str:
    """Elapsed seconds since app start.

    Returns:
        Elapsed time string.
    """
    return f"{time.time() - T0:.1f}"


class BgState(rx.State):
    """Holds the background-task progress log."""

    log: list[str] = []
    runs: int = 0

    async def _steps(self, label: str):
        """Write 4 timestamped steps 1s apart under the given label.

        Args:
            label: Prefix for the log entries.
        """
        for i in range(1, 5):
            await asyncio.sleep(1.0)
            async with self:
                self.log.append(f"{ts()}|{label}-step{i}")

    @rx.event(background=True)
    async def bg_on_load(self):
        """Background on_load for /slowbg."""
        async with self:
            self.runs += 1
            n = self.runs
            self.log.append(f"{ts()}|load{n}-start")
        await self._steps(f"load{n}")

    @rx.event(background=True)
    async def bg_on_click(self):
        """Identical background task, but started from a button."""
        async with self:
            self.log.append(f"{ts()}|btn-start")
        await self._steps("btn")

    @rx.event
    def do_log(self):
        """Emit worker-side log records (FINDING-005 full-logging probe)."""
        import logging

        from reflex_base.utils import console

        console.info("worker console.info from event handler")
        console.warn("worker console.warn from event handler")
        logging.getLogger("reflex_base.probe").info("worker hierarchy logger record")

    @rx.event
    def clear(self):
        """Reset the log."""
        self.log = []
        self.runs = 0


def shell(*kids: rx.Component) -> rx.Component:
    """Shared page layout.

    Args:
        kids: Page content.

    Returns:
        The layout component.
    """
    return rx.container(
        rx.vstack(
            rx.hstack(
                rx.link("home", href="/", id="lnk-home"),
                rx.link("slowbg", href="/slowbg", id="lnk-slowbg"),
                rx.link("other", href="/other", id="lnk-other"),
                rx.link("charts", href="/charts", id="lnk-charts"),
                rx.link("dyn", href="/dyn", id="lnk-dyn"),
                spacing="4",
            ),
            *kids,
            rx.box("LOG: ", BgState.log.join(" ; "), id="bg-log"),
            align="start",
            spacing="4",
        ),
        padding="2em",
    )


@rx.page(route="/", title="home")
def index() -> rx.Component:
    """Home page.

    Returns:
        The page component.
    """
    return shell(rx.heading("HOME", id="hd"))


@rx.page(route="/slowbg", title="slowbg", on_load=BgState.bg_on_load)
def slowbg() -> rx.Component:
    """Page whose on_load is a background task.

    Returns:
        The page component.
    """
    return shell(rx.heading("SLOWBG", id="hd"))


@rx.page(route="/other", title="other")
def other() -> rx.Component:
    """Plain navigation target with a bg-task button.

    Returns:
        The page component.
    """
    return shell(
        rx.heading("OTHER", id="hd"),
        rx.button("start bg", on_click=BgState.bg_on_click, id="btn-bg"),
        rx.button("clear", on_click=BgState.clear, id="btn-clear"),
    )


class ChartState(rx.State):
    """State holding a plotly figure (FINDING-020 id-prop probe)."""

    bump: int = 0

    @rx.var
    def fig(self) -> go.Figure:
        """A tiny bar chart figure.

        Returns:
            The plotly figure.
        """
        return go.Figure(data=[go.Bar(x=[1, 2, 3], y=[3, 1, 2 + self.bump])])

    @rx.event
    def bump_it(self):
        """Change the figure data."""
        self.bump += 1


@rx.page(route="/charts", title="charts")
def charts() -> rx.Component:
    """Plotly page: state-var figure with id=, plus a static control box.

    Returns:
        The page component.
    """
    return shell(
        rx.heading("CHARTS", id="hd"),
        rx.box("control", id="control-box"),
        rx.plotly(data=ChartState.fig, id="the-plot", width="420px", height="260px"),
        rx.button("bump", on_click=ChartState.bump_it, id="btn-bump"),
    )


class DynState(rx.State):
    """Dynamic-component state for the FINDING-017 probe."""

    label: str = "start"

    @rx.var
    def dyn_block(self) -> rx.Component:
        """Computed dynamic component using a lucide icon (subpath import).

        Returns:
            The dynamic component.
        """
        return rx.vstack(
            rx.icon("apple", id="dyn-icon"),
            rx.text(f"label: {self.label}", id="dyn-label"),
        )

    @rx.event
    def relabel(self):
        """Change the label inside the dynamic component."""
        self.label = "clicked"


@rx.page(route="/dyn", title="dyn")
def dyn() -> rx.Component:
    """Dynamic component page.

    Returns:
        The page component.
    """
    return shell(
        rx.heading("DYN", id="hd"),
        rx.icon("banana", id="static-icon"),
        DynState.dyn_block,
        rx.button("relabel", on_click=DynState.relabel, id="btn-relabel"),
    )


app = rx.App()
