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
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

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

app = rx.App(
    api_transformer=Starlette(routes=[Route("/reload-version", reload_version)]),
)
app.add_page(index, route="/")
{page_registrations}
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
        rx.text(
            rx.cond(State.is_hydrated, "hydrated", "loading"),
            id="hydrated",
        ),
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

class RowState(rx.State):
    rows: list[str] = []
    selected: int = -1

    def create_rows(self):
        self.rows = [f"row {index}" for index in range(1000)]

    def partial_update(self):
        for index in range(0, len(self.rows), 10):
            self.rows[index] += " !!!"

    def select_row(self, index: int):
        self.selected = index

    def swap_rows(self):
        self.rows[1], self.rows[998] = self.rows[998], self.rows[1]

def rows():
    return rx.vstack(
        rx.text(
            rx.cond(RowState.is_hydrated, "hydrated", "loading"),
            id="rows-hydrated",
        ),
        rx.text(RowState.selected, id="selected-row"),
        rx.button("create", id="create-rows", on_click=RowState.create_rows),
        rx.button("partial", id="partial-update", on_click=RowState.partial_update),
        rx.button("swap", id="swap-rows", on_click=RowState.swap_rows),
        rx.foreach(
            RowState.rows,
            lambda row, index: rx.text(
                row,
                id=f"row-{index}",
                class_name=rx.cond(index == RowState.selected, "row selected", "row"),
                on_click=RowState.select_row(index),
            ),
        ),
    )

app = rx.App()
app.add_page(index)
app.add_page(second, route="/second")
app.add_page(rows, route="/rows")
"""
