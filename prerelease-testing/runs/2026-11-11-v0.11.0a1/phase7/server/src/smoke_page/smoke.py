"""phase7 smoke: blank-template app page with an event and a background task."""

import asyncio
import os

import reflex as rx

_V = os.environ.get("EXPECT_VENV", "")
assert _V and rx.__file__.startswith(_V + "/"), (_V, rx.__file__)


class State(rx.State):
    count: int = 0
    bg: int = 0
    bg_running: bool = False
    pid: str = ""

    @rx.event
    def inc(self):
        self.count += 1
        self.pid = str(os.getpid())

    @rx.event(background=True)
    async def run_bg(self):
        async with self:
            self.bg_running = True
        for _ in range(5):
            await asyncio.sleep(0.3)
            async with self:
                self.bg += 1
        async with self:
            self.bg_running = False


def index() -> rx.Component:
    return rx.container(
        rx.heading("smoke"),
        rx.text("count=", State.count, id="count"),
        rx.text("bg=", State.bg, id="bg"),
        rx.text(rx.cond(State.bg_running, "running", "idle"), id="bgstate"),
        rx.text("pid=", State.pid, id="pid"),
        rx.button("inc", on_click=State.inc, id="inc"),
        rx.button("bg", on_click=State.run_bg, id="runbg"),
    )


app = rx.App()
app.add_page(index)
