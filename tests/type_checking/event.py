"""Inferred types for `reflex_base.event` that are part of the public contract."""

from collections.abc import Callable, Sequence
from typing import Any, ClassVar, assert_type

from reflex_base.event import (
    EventCallback,
    EventHandler,
    EventSpec,
    EventType,
    IdentityEventReturn,
    LambdaEventCallback,
    event,
    passthrough_event_spec,
)
from reflex_base.vars.base import Var

import reflex as rx
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
assert_type(_HandlerState.no_args(), EventSpec)
assert_type(_HandlerState.one(1), EventSpec)
assert_type(_HandlerState.one(_index), EventSpec)
assert_type(_HandlerState.two(_index, "a"), EventSpec)
assert_type(_HandlerState.three(1, "a", True), EventSpec)
assert_type(_HandlerState.four(1, "a", True, 1.5), EventSpec)
assert_type(_HandlerState.five(_index, "a", True, 1.5, b""), EventSpec)
assert_type(_HandlerState.six(1, "a", True, 1.5, b"", _index), EventSpec)
assert_type(_HandlerState.seven(1, "a", True, 1.5, b"", _index, "b"), EventSpec)
assert_type(_HandlerState.eight(_index, "a", True, 1.5, b"", 2, "b", False), EventSpec)

# Called with no arguments when parameters remain, it still takes all of them.
assert_type(_HandlerState.one(), EventCallback[int])
assert_type(_HandlerState.two(), EventCallback[int, str])

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

# An event spec passes a trigger's values on as Vars of the given types. A
# union, such as `str | None`, makes a Var of any value.
assert_type(passthrough_event_spec(str), Callable[[Var[str]], tuple[Var[str]]])
assert_type(
    passthrough_event_spec(int, str),
    Callable[[Var[int], Var[str]], tuple[Var[int], Var[str]]],
)
assert_type(passthrough_event_spec(str | None), Callable[[Var[Any]], tuple[Var[Any]]])
assert_type(
    passthrough_event_spec(str | int, dict),
    Callable[[Var[Any], Var[Any]], tuple[Var[Any], Var[Any]]],
)
assert_type(
    passthrough_event_spec(int, str | None),
    Callable[[Var[Any], Var[Any]], tuple[Var[Any], Var[Any]]],
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
    on_submit: EventHandler
    on_either: EventHandler | EventCallback[()]


class _HandlerHolderState(State):
    on_submit: ClassVar[EventHandler]


def _reads(state: _State, holder: _Holder, handler_state: _HandlerHolderState) -> None:
    # Read through its state class, a handler is the callback event triggers take.
    assert_type(_State.set_name, EventCallback[str])
    # Read through an instance of that state, it is the function bound to it.
    assert_type(state.set_name, Callable[[str], Any])
    # Stored anywhere else, e.g. a component or dataclass field, it stays the
    # callback: only a state instance binds it.
    assert_type(holder.on_name, EventCallback[str] | None)
    assert_type(holder.on_submit, EventHandler)
    assert_type(holder.on_either, EventHandler | EventCallback[()])
    _event_prop(holder.on_either)
    # A handler read through an instance of a state is bound to it, so it is
    # whatever function it wraps.
    assert_type(_HandlerHolderState.on_submit, EventHandler)
    assert_type(handler_state.on_submit, Callable[..., Any])


def _namespace_annotations(
    callback: event.EventCallback[str],
    lambda_callback: event.LambdaEventCallback[str],
    identity: event.IdentityEventReturn[int],
    event_type: event.EventType[str],
    spec: event.EventSpec,
) -> None:
    # The event namespace (`rx.event`) re-exports the event types, generic or
    # not, for annotations.
    assert_type(callback, EventCallback[str])
    assert_type(lambda_callback, LambdaEventCallback[str])
    assert_type(identity, IdentityEventReturn[int])
    assert_type(event_type, EventType[str])
    assert_type(spec, EventSpec)
    _event_prop(_HandlerState.one(1))


class _RepeatedState(State):
    @event(throttle=300)
    @event(background=True)
    async def configured_twice(self, step: int) -> None: ...

    @event
    @event(throttle=300)
    def bare_over_configured(self, step: int, label: str) -> None: ...

    @event(stop_propagation=True)
    @event
    def configured_over_bare(self) -> None: ...


# A repeated @rx.event is one handler, typed like a single decorator.
assert_type(_RepeatedState.configured_twice, EventCallback[int])
assert_type(_RepeatedState.bare_over_configured, EventCallback[int, str])
assert_type(_RepeatedState.configured_over_bare, EventCallback[()])

# Event actions keep the EventSpec return type on complete calls and the
# EventCallback return type on partial calls.
assert_type(_HandlerState.no_args().stop_propagation, EventSpec)
assert_type(_HandlerState.no_args.stop_propagation(), EventSpec)
assert_type(
    _HandlerState.one(1).prevent_default.throttle(300).debounce(100).temporal,
    EventSpec,
)
assert_type(_HandlerState.one.prevent_default(1), EventSpec)
assert_type(_HandlerState.two(1).stop_propagation, EventCallback[str])


@event
def _decentralized(state: _HandlerState, count: int) -> None: ...


assert_type(_decentralized(1), EventSpec)


class _ChainedState(State):
    @event
    def reset_count(self) -> None: ...

    @event
    def increment(self, by: int) -> None: ...

    @event
    def pair(self, index: int, label: str) -> None: ...

    @event
    def chain_zero(self) -> EventSpec:
        return _ChainedState.reset_count()

    @event
    def chain_one(self) -> EventSpec:
        return _ChainedState.increment(1)

    @event
    def chain_actions(self) -> EventSpec:
        return _ChainedState.pair(1, "a").stop_propagation

    @event
    def chain_optional(self, send: bool) -> EventSpec | None:
        return _ChainedState.increment(1) if send else None

    @event
    def chain_list(self) -> list[EventSpec]:
        return [_ChainedState.reset_count(), _ChainedState.increment(1)]

    @event
    def chain_sequence(self) -> Sequence[EventSpec]:
        return (_ChainedState.reset_count(), _ChainedState.pair(1, "a"))

    @event
    async def await_chained(self) -> None:
        await _ChainedState.reset_count()
        await _ChainedState.increment(1)


_event_prop(_ChainedState.reset_count())
_event_prop(_ChainedState.increment(1).stop_propagation)
rx.button("Click", on_click=_ChainedState.increment(1))
rx.button(
    "Click both", on_click=[_ChainedState.reset_count, _ChainedState.increment(1)]
)
rx.input(on_blur=_ChainedState.pair(1))
