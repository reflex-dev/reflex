"""#7668 probe: JSON log records inside an OTel span carry trace_id/span_id."""

import contextlib
import logging
import os

import reflex as rx
from reflex_base.utils import console

VENV = os.environ.get("NA_VENV", "")
assert VENV and f"/envs/{VENV}/" in rx.__file__, (VENV, rx.__file__)

if os.environ.get("OA_INSTRUMENT", "1") == "1":
    from reflex_otel import ReflexInstrumentor

    ReflexInstrumentor().instrument()

ulog = logging.getLogger("otelapp")
rlog = logging.getLogger("reflex.otelapp")
ulog.warning("OA user-logger at import (outside span)")
rlog.warning("OA reflex-logger at import (outside span)")


class S(rx.State):
    n: int = 0

    @rx.event
    def go(self):
        ulog.warning("OA user-logger inside handler")
        rlog.warning("OA reflex-logger inside handler")
        console.warn("OA console.warn inside handler")
        print("OA print inside handler", flush=True)
        self.n += 1
        return S.chained

    @rx.event
    def chained(self):
        rlog.warning("OA reflex-logger inside chained")

    @rx.event(background=True)
    async def bg(self):
        rlog.warning("OA reflex-logger inside bg task")
        async with self:
            self.n += 10

    @rx.event
    def boom(self):
        raise ValueError("OA boom in handler")


def index():
    return rx.vstack(
        rx.heading("otel", id="page"),
        rx.text("n=", S.n, id="n"),
        rx.button("go", on_click=S.go, id="go"),
        rx.button("bg", on_click=S.bg, id="bg"),
        rx.button("boom", on_click=S.boom, id="boom"),
    )


app = rx.App()
app.add_page(index)


@app.register_lifespan_task
@contextlib.asynccontextmanager
async def task():
    rlog.warning("OA reflex-logger in lifespan task (outside span)")
    yield
