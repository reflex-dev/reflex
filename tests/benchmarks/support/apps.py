"""Representative Reflex application sources for lifecycle and load tests."""

from __future__ import annotations


def lifecycle_app_source(
    rows: int = 100,
    pages: int = 1,
    reload_version: int = 0,
) -> str:
    """Create a deterministic multi-page application source.

    Args:
        rows: Number of stateful rows per page.
        pages: Number of routes.
        reload_version: Value exposed by the backend reload probe.

    Returns:
        Python source for a Reflex application.
    """
    page_registrations = "\n".join(
        f'app.add_page(lambda route="page-{index}": index(route), route="/page-{index}")'
        for index in range(pages)
    )
    return f"""import reflex as rx
from starlette.responses import JSONResponse

RELOAD_VERSION = {reload_version}

class State(rx.State):
    count: int = 0

    def increment(self):
        self.count += 1

def row(index: int):
    return rx.hstack(rx.text(index), rx.text(State.count))

def index(label: str = "index"):
    return rx.vstack(
        rx.heading(label),
        rx.button("increment", on_click=State.increment),
        *[row(index) for index in range({rows})],
    )

async def reload_version(_request):
    return JSONResponse({{"version": RELOAD_VERSION}})

app = rx.App()
app.add_page(index, route="/")
{page_registrations}
app._api.add_route("/reload-version", reload_version)
"""


def load_app_source() -> str:
    """Create an app covering the load-test handler scenarios.

    Returns:
        Python source for a production-mode Reflex load app.
    """
    return """import asyncio
import time
import reflex as rx

class State(rx.State):
    count: int = 0
    values: list[int] = []

    def increment(self):
        self.count += 1

    async def async_io(self):
        await asyncio.sleep(0.01)
        self.count += 1

    def blocking(self):
        time.sleep(0.02)
        self.count += 1

    def stream(self):
        for _ in range(3):
            self.count += 1
            yield

    def append_large(self):
        self.values.extend(range(1000))

def index():
    return rx.vstack(
        rx.text(State.count, id="count"),
        rx.button("increment", id="increment", on_click=State.increment),
        rx.button("async", id="async-io", on_click=State.async_io),
        rx.button("blocking", id="blocking", on_click=State.blocking),
        rx.button("stream", id="stream", on_click=State.stream),
        rx.button("large", id="append-large", on_click=State.append_large),
        rx.foreach(State.values, lambda value: rx.text(value, class_name="value-row")),
        rx.link("second", href="/second", id="second-link"),
    )

def second():
    return rx.heading("Second page", id="second-heading")

app = rx.App()
app.add_page(index)
app.add_page(second, route="/second")
"""
