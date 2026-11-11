"""A small typed app module, the way a user with pyright/mypy in CI writes one.

Exercises #7715 (mypy: handlers are EventCallback), #7752 (5-8 positional values),
#7755 (a stored EventHandler reads back as the handler), #7754 (FunctionStringVar _var_type=EventChain)
and the awaitable handlers of #7673.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from typing import Any

import reflex as rx
from reflex.event import EventCallback, EventChain, EventHandler, EventSpec, EventType
from reflex.vars.function import FunctionStringVar


class S(rx.State):
    count: int = 0
    items: list[str] = []

    @rx.event
    def no_args(self) -> None:
        self.count = 0

    @rx.event
    def one(self, v: int) -> None:
        self.count = v

    @rx.event
    def two(self, v: int, w: str) -> None:
        self.count = v

    @rx.event
    def five(self, a: int, b: str, c: bool, d: float, e: bytes) -> None:
        self.count = a

    @rx.event
    def eight(
        self, a: int, b: str, c: bool, d: float, e: bytes, f: int, g: str, h: bool
    ) -> None:
        self.count = a

    @rx.event
    def nine(
        self, a: int, b: str, c: bool, d: float, e: bytes, f: int, g: str, h: bool, i: float
    ) -> None:
        self.count = a

    @rx.event
    def add(self, amount: int) -> int:
        self.count += amount
        return self.count

    @rx.event
    async def aadd(self, amount: int) -> int:
        self.count += amount
        return self.count

    @rx.event(background=True)
    async def bg(self) -> None:
        async with self:
            self.count += 1

    @rx.event(throttle=100)
    def throttled(self, v: str) -> None:
        self.items.append(v)

    @rx.event(supersedes=True)
    async def search(self, q: str) -> list[str]:
        return [q]

    @rx.event
    def on_text(self, v: str) -> None:
        self.items.append(v)

    @rx.event
    def returns_spec(self) -> rx.event.EventSpec:
        return rx.redirect("/")

    @rx.event
    def returns_specs(self) -> list[EventSpec]:
        return [rx.redirect("/"), rx.toast("x")]

    @rx.event
    def chain(self):
        return [S.one(1), S.five(1, "a", True, 1.0, b"")]

    @rx.event
    async def caller(self):
        # awaitable handlers (#7673)
        first = await type(self).add(1)
        second = await S.add(2)
        third = await S.aadd(3)
        hits = await S.search("q")
        await S.no_args()
        await S.no_args
        # self.handler() is still the plain method
        direct: int = self.add(3)
        also: int = await self.aadd(3)
        self.no_args()
        self.count = first + second + third + direct + also + len(hits)
        yield S.one(1)
        yield rx.toast("done")

    @rx.event(background=True)
    async def bg_caller(self) -> None:
        total = await S.add(1)
        async with self:
            self.count = total


@dataclasses.dataclass
class Holder:
    """A handler stored outside a state (#7755)."""

    on_submit: EventHandler
    on_text: EventCallback[str] | None = None


def takes_handler(h: EventHandler) -> None: ...


def takes_event(e: EventType[()]) -> None: ...


def takes_text_event(e: EventType[str]) -> None: ...


def takes_callable(f: Callable[[int], Any]) -> None: ...


holder = Holder(on_submit=S.no_args, on_text=S.on_text)
stored: EventHandler = holder.on_submit
takes_handler(holder.on_submit)
takes_handler(S.no_args)
takes_event(S.no_args)
takes_event(S.one(1))
takes_event(S.eight(1, "a", True, 1.5, b"", 2, "b", False))
takes_event([S.no_args, S.one(1), rx.toast("x")])
takes_text_event(S.on_text)
takes_callable(S.one)
spec: EventSpec = S.one(1)
partial_five: EventCallback[bool, float, bytes] = S.five(1, "a")


def index() -> rx.Component:
    return rx.vstack(
        rx.button("a", on_click=S.no_args),
        rx.button("b", on_click=S.one(1)),
        rx.button("c", on_click=S.five(1, "a", True, 1.5, b"")),
        rx.button("d", on_click=S.eight(1, "a", True, 1.5, b"", 2, "b", False)),
        rx.button("d9", on_click=S.nine(1, "a", True, 1.5, b"", 2, "b", False, 2.5)),
        rx.button("e", on_click=lambda: S.one(1)),
        rx.button("f", on_click=[S.no_args, rx.toast("hi")]),
        rx.button("g", on_click=S.bg),
        rx.button("h", on_click=S.add(1)),
        rx.button("i", on_click=S.caller),
        rx.button("j", on_click=S.one(S.count)),
        rx.button("k", on_click=S.search("q")),
        rx.button("l", on_click=S.one(1).stop_propagation),
        rx.button("m", on_click=S.one(1).throttle(100)),
        rx.input(on_change=S.on_text),
        rx.input(on_change=S.throttled),
        rx.input(on_blur=S.two(1)),
        rx.el.div(on_mount=FunctionStringVar.create("() => {}", _var_type=EventChain)),
        rx.button("n", on_click=holder.on_submit),
    )


app = rx.App()
app.add_page(index, on_load=S.no_args)
app.add_page(index, route="/two", on_load=[S.no_args, S.one(1)])
