"""Inferred types for `reflex_base.event` that are part of the public contract."""

from collections.abc import Callable
from typing import Any, assert_type

from reflex_base.event import EventCallback, event
from reflex_base.vars.base import Var

from reflex.state import State


class _HandlerState(State):
    @event
    def no_args(self) -> None: ...

    @event
    def one(self, index: int) -> None: ...

    @event
    def two(self, index: int, value: str) -> None: ...

    @event
    def three(self, index: int, value: str, flag: bool) -> None: ...

    @event
    def four(self, index: int, value: str, flag: bool, count: float) -> None: ...


_index: Var[int] = Var("index")

# A handler called with all of its arguments, plain or as Vars, is a complete event.
assert_type(_HandlerState.no_args(), EventCallback[()])
assert_type(_HandlerState.one(1), EventCallback[()])
assert_type(_HandlerState.one(_index), EventCallback[()])
assert_type(_HandlerState.two(_index, "a"), EventCallback[()])
assert_type(_HandlerState.three(1, "a", True), EventCallback[()])
assert_type(_HandlerState.four(1, "a", True, 1.5), EventCallback[()])

# Called with the leading arguments, it still takes the rest, e.g. from the event.
assert_type(_HandlerState.two(_index), EventCallback[str])
assert_type(_HandlerState.three(_index), EventCallback[str, bool])
assert_type(_HandlerState.three(1, "a"), EventCallback[bool])
assert_type(_HandlerState.four(_index), EventCallback[str, bool, float])
assert_type(_HandlerState.four(1, "a", True), EventCallback[float])

# A handler is a callable of its arguments, so it can be passed where one is expected.
_one: Callable[[int], Any] = _HandlerState.one
_two: Callable[[int, str], Any] = _HandlerState.two


class _State(State):
    @event
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
