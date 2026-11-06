"""Inferred types for `reflex_base.event` that are part of the public contract."""

from collections.abc import Callable
from typing import Any, assert_type

from reflex_base.event import EventCallback, EventSpec, EventType, event
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

    @event
    def five(self, a: int, b: str, c: bool, d: float, e: bytes) -> None: ...

    @event
    def six(self, a: int, b: str, c: bool, d: float, e: bytes, f: int) -> None: ...

    @event
    def seven(
        self, a: int, b: str, c: bool, d: float, e: bytes, f: int, g: str
    ) -> None: ...

    @event
    def eight(
        self, a: int, b: str, c: bool, d: float, e: bytes, f: int, g: str, h: bool
    ) -> None: ...

    @event
    def nine(
        self,
        a: int,
        b: str,
        c: bool,
        d: float,
        e: bytes,
        f: int,
        g: str,
        h: bool,
        i: float,
    ) -> None: ...


_index: Var[int] = Var("index")

# A handler called with all of its arguments, plain or as Vars, is a complete event.
assert_type(_HandlerState.no_args(), EventCallback[()])
assert_type(_HandlerState.one(1), EventCallback[()])
assert_type(_HandlerState.one(_index), EventCallback[()])
assert_type(_HandlerState.two(_index, "a"), EventCallback[()])
assert_type(_HandlerState.three(1, "a", True), EventCallback[()])
assert_type(_HandlerState.four(1, "a", True, 1.5), EventCallback[()])
assert_type(_HandlerState.five(_index, "a", True, 1.5, b""), EventCallback[()])
assert_type(_HandlerState.six(1, "a", True, 1.5, b"", _index), EventCallback[()])
assert_type(_HandlerState.seven(1, "a", True, 1.5, b"", _index, "b"), EventCallback[()])
assert_type(
    _HandlerState.eight(_index, "a", True, 1.5, b"", 2, "b", False), EventCallback[()]
)

# Called with the leading arguments, it still takes the rest, e.g. from the event.
assert_type(_HandlerState.two(_index), EventCallback[str])
assert_type(_HandlerState.three(_index), EventCallback[str, bool])
assert_type(_HandlerState.three(1, "a"), EventCallback[bool])
assert_type(_HandlerState.four(_index), EventCallback[str, bool, float])
assert_type(_HandlerState.four(1, "a", True), EventCallback[float])
assert_type(_HandlerState.five(1, "a"), EventCallback[bool, float, bytes])
assert_type(_HandlerState.seven(1, "a", True, 1.5), EventCallback[bytes, int, str])
assert_type(_HandlerState.seven(1, "a", True, 1.5, b""), EventCallback[int, str])
assert_type(_HandlerState.six(1, "a", True, 1.5, b""), EventCallback[int])
assert_type(_HandlerState.seven(1, "a", True, 1.5, b"", 2), EventCallback[str])
assert_type(_HandlerState.eight(1, "a", True, 1.5, b"", 2, "b"), EventCallback[bool])
assert_type(
    _HandlerState.nine(1, "a", True, 1.5, b"", 2, "b", False), EventCallback[float]
)

# A handler is a callable of its arguments, so it can be passed where one is expected.
_one: Callable[[int], Any] = _HandlerState.one
_two: Callable[[int, str], Any] = _HandlerState.two


def _event_prop(value: EventType[()]) -> None: ...


def _event_sequences(
    specs: list[EventSpec], handlers: tuple[EventCallback[()], ...]
) -> None:
    # An event prop takes a list variable of events, not only a list literal,
    # and a tuple of them.
    _event_prop(specs)
    _event_prop(handlers)


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
