"""Event handlers with 0..5 arguments: called with literals/Vars, partially applied, passed uncalled.

Everything in this file is valid Reflex usage; a type checker should report no errors except on the
lines marked `# expect-error` (deliberate misuse, to prove the checker is actually checking).
"""

from collections.abc import Callable
from typing import Any

from reflex_base.event import EventCallback
from typing_extensions import assert_type

import reflex as rx


class Shop(rx.State):
    """Handlers with every fixed arity from 0 to 5."""

    qty: int = 3
    name: str = "Notebook"
    enabled: bool = True
    price: float = 4.5
    tag: str = "new"

    @rx.event
    def h0(self) -> None:
        """No arguments."""

    @rx.event
    def h1(self, qty: int) -> None:
        """One argument."""
        self.qty = qty

    @rx.event
    def h2(self, qty: int, name: str) -> None:
        """Two arguments."""

    @rx.event
    def h3(self, qty: int, name: str, enabled: bool) -> None:
        """Three arguments."""

    @rx.event
    def h4(self, qty: int, name: str, enabled: bool, price: float) -> None:
        """Four arguments."""

    @rx.event
    def h5(self, qty: int, name: str, enabled: bool, price: float, tag: str) -> None:
        """Five arguments."""

    @rx.event
    def on_text(self, value: str) -> None:
        """Matches on_change of an input (one str)."""
        self.name = value


# fully applied with literals
assert_type(Shop.h0(), EventCallback[()])
assert_type(Shop.h1(1), EventCallback[()])
assert_type(Shop.h2(1, "a"), EventCallback[()])
assert_type(Shop.h3(1, "a", True), EventCallback[()])
assert_type(Shop.h4(1, "a", True, 1.5), EventCallback[()])
assert_type(Shop.h5(1, "a", True, 1.5, "t"), EventCallback[()])
# fully applied with Vars
assert_type(Shop.h1(Shop.qty), EventCallback[()])
assert_type(Shop.h2(Shop.qty, Shop.name), EventCallback[()])
assert_type(Shop.h3(Shop.qty, Shop.name, Shop.enabled), EventCallback[()])
assert_type(Shop.h4(Shop.qty, Shop.name, Shop.enabled, Shop.price), EventCallback[()])
assert_type(Shop.h5(Shop.qty, Shop.name, Shop.enabled, Shop.price, Shop.tag), EventCallback[()])
# partially applied (mix of literals and Vars)
assert_type(Shop.h2(Shop.qty), EventCallback[str])
assert_type(Shop.h3(1), EventCallback[str, bool])
assert_type(Shop.h4(Shop.qty, "a"), EventCallback[bool, float])
assert_type(Shop.h5(1, Shop.name, True), EventCallback[float, str])
# handlers where a plain callable of their args is expected
c0: Callable[[], Any] = Shop.h0
c1: Callable[[int], Any] = Shop.h1
c2: Callable[[int, str], Any] = Shop.h2
c3: Callable[[int, str, bool], Any] = Shop.h3
c4: Callable[[int, str, bool, float], Any] = Shop.h4
c5: Callable[[int, str, bool, float, str], Any] = Shop.h5


def page() -> rx.Component:
    """Handlers passed uncalled and called to component triggers."""
    return rx.vstack(
        rx.button("h0", on_click=Shop.h0),
        rx.button("h1", on_click=Shop.h1(2)),
        rx.button("h5", on_click=Shop.h5(1, "a", True, 1.5, "t")),
        rx.button("h5 vars", on_click=Shop.h5(Shop.qty, Shop.name, Shop.enabled, Shop.price, Shop.tag)),
        rx.button("chain", on_click=[Shop.h0, Shop.h2(1, "b"), Shop.h4(1, "a", False, 2.0)]),
        rx.input(on_change=Shop.on_text),
        rx.input(on_blur=Shop.on_text),
        rx.input(on_change=Shop.h2(Shop.qty)),
    )


# deliberate misuse: a checker that reports nothing here is not checking
Shop.h2("not-an-int", "a")  # expect-error
Shop.h5(1, "a", True, 1.5, "t", "extra")  # expect-error
