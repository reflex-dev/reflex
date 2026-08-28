"""Minimal verifier app: is a background-task on_load cancelled by navigation?

Pages:
- /slowbg : on_load is @rx.event(background=True) writing 5 log entries ~1s apart
- /other  : plain target page; has a button that starts the SAME kind of
            background task (for the button-vs-on_load contrast)
"""

import asyncio
import time

import reflex as rx

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


app = rx.App()
