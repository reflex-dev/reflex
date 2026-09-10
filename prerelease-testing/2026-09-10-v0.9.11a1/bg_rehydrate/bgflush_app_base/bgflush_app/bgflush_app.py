"""Repro app for reflex-dev/reflex#6995: background handler delta flush when the handler raises.

Pages:
  /            buttons that trigger the background handler variants
  /other       same page under another route (router-derived text changes)
  /onload-bg   page whose on_load IS a raising no-context background handler

API (mounted via api_transformer):
  GET /api/state   -> {"beats": <times State.beat was computed>, "exc": [...handled exceptions...],
                       "flush_fail": bool}
  GET /api/reset   -> zero the counters
"""

import asyncio
import os

import reflex as rx
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

BEATS = {"n": 0}
EXC: list[str] = []
FLUSH_FAIL = {"on": False}


class State(rx.State):
    count: int = 0
    note: str = "-"

    @rx.var(cache=False)
    def beat(self) -> int:
        """Uncached computed var: recomputed (and sent) on every delta flush."""
        BEATS["n"] += 1
        if FLUSH_FAIL["on"]:
            msg = "flush boom (uncached var raised during delta resolution)"
            raise ValueError(msg)
        return BEATS["n"]

    @rx.var
    def where(self) -> str:
        """Router-derived text (depends on router_data set by the event preamble)."""
        return f"path={self.router.url.path} q={self.router.url.query}"

    @rx.event(background=True)
    async def bg_raises_noctx(self):
        """Never enters `async with self`, mutates nothing, raises."""
        await asyncio.sleep(0.05)
        msg = "boom-noctx"
        raise RuntimeError(msg)

    @rx.event(background=True)
    async def bg_raises_after_ctx(self):
        async with self:
            self.count += 1
            self.note = "after-ctx: mutated, about to raise outside ctx"
        msg = "boom-after-ctx"
        raise RuntimeError(msg)

    @rx.event(background=True)
    async def bg_raises_inside_ctx(self):
        async with self:
            self.count += 1
            self.note = "inside-ctx: mutated, raising inside ctx"
            msg = "boom-inside-ctx"
            raise RuntimeError(msg)

    @rx.event(background=True)
    async def bg_yields_then_raises(self):
        """Yields a frontend event (no ctx) then raises."""
        yield rx.toast.info("yielded-before-raise")
        await asyncio.sleep(0.05)
        msg = "boom-after-yield"
        raise RuntimeError(msg)

    @rx.event(background=True)
    async def bg_yields_state_event_then_raises(self):
        """Yields a STATE event handler (no ctx) then raises."""
        yield State.bump_note
        await asyncio.sleep(0.05)
        msg = "boom-after-yield-state-event"
        raise RuntimeError(msg)

    @rx.event(background=True)
    async def bg_flush_fails(self):
        """Raise, and make the compat flush itself fail (uncached var raises)."""
        FLUSH_FAIL["on"] = True
        msg = "boom-flush-fails"
        raise RuntimeError(msg)

    @rx.event(background=True)
    async def bg_ok_noctx(self):
        """Control: no ctx, no raise."""
        await asyncio.sleep(0.05)

    @rx.event
    def bump_note(self):
        self.note = "bump_note ran"

    @rx.event
    def fg_noop(self):
        """Foreground control event."""

    @rx.event
    def clear_flush_fail(self):
        FLUSH_FAIL["on"] = False
        self.note = "flush_fail cleared"


def exc_handler(exception: Exception) -> rx.event.EventSpec:
    EXC.append(f"{type(exception).__name__}: {exception}")
    return rx.toast.error(f"handled: {type(exception).__name__}: {exception}", id="bexc")


async def api_state(_request):
    return JSONResponse({"beats": BEATS["n"], "exc": list(EXC), "flush_fail": FLUSH_FAIL["on"]})


async def api_reset(_request):
    BEATS["n"] = 0
    EXC.clear()
    FLUSH_FAIL["on"] = False
    return JSONResponse({"ok": True})


def controls() -> rx.Component:
    return rx.vstack(
        rx.heading("bgflush"),
        rx.text("beat=", State.beat, id="beat"),
        rx.text("count=", State.count, id="count"),
        rx.text("note=", State.note, id="note"),
        rx.text("where=", State.where, id="where"),
        rx.hstack(
            rx.button("noctx-raise", id="b-noctx", on_click=State.bg_raises_noctx),
            rx.button("after-ctx-raise", id="b-after", on_click=State.bg_raises_after_ctx),
            rx.button("inside-ctx-raise", id="b-inside", on_click=State.bg_raises_inside_ctx),
            rx.button("yield-then-raise", id="b-yield", on_click=State.bg_yields_then_raises),
            rx.button("yield-state-then-raise", id="b-yieldstate", on_click=State.bg_yields_state_event_then_raises),
            wrap="wrap",
        ),
        rx.hstack(
            rx.button("flush-fails", id="b-flushfail", on_click=State.bg_flush_fails),
            rx.button("clear-flush-fail", id="b-clearff", on_click=State.clear_flush_fail),
            rx.button("ok-noctx", id="b-ok", on_click=State.bg_ok_noctx),
            rx.button("fg-noop", id="b-fg", on_click=State.fg_noop),
            wrap="wrap",
        ),
        rx.hstack(
            rx.link("to /", href="/", id="l-index"),
            rx.link("to /other", href="/other", id="l-other"),
            rx.link("to /other?x=1", href="/other?x=1", id="l-otherq"),
            rx.link("to /onload-bg", href="/onload-bg", id="l-onload"),
        ),
        spacing="3",
        padding="1em",
    )


def index() -> rx.Component:
    return controls()


def other() -> rx.Component:
    return controls()


def onload_bg() -> rx.Component:
    return rx.vstack(rx.heading("onload-bg"), controls())


api = Starlette(routes=[Route("/api/state", api_state), Route("/api/reset", api_reset)])

kwargs = {}
if not os.environ.get("BGFLUSH_DEFAULT_HANDLER"):
    kwargs["backend_exception_handler"] = exc_handler
app = rx.App(api_transformer=api, **kwargs)
app.add_page(index, route="/")
app.add_page(other, route="/other")
app.add_page(onload_bg, route="/onload-bg", on_load=State.bg_raises_noctx)
