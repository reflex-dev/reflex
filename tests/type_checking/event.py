"""Inferred types for `reflex_base.event` that are part of the public contract."""

from collections.abc import Callable
from typing import Any

from reflex_base.event import EventCallback
from typing_extensions import assert_type

import reflex as rx


class _State(rx.State):
    @rx.event
    def set_name(self, name: str) -> None: ...


class _Holder:
    on_name: EventCallback[str] | None = None


def _reads(state: _State, holder: _Holder) -> None:
    # Read through its state class, a handler is the callback event triggers take.
    assert_type(_State.set_name, EventCallback[str])
    # Read through an instance of that state, it is the function bound to it.
    assert_type(state.set_name, Callable[[str], Any])
    # Stored anywhere else, e.g. a component or dataclass field, it stays the
    # callback: only a state instance binds it.
    assert_type(holder.on_name, EventCallback[str] | None)
