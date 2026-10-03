"""Inferred types for `reflex_base.event` that are part of the public contract."""

from reflex_base.event import EventCallback, EventSpec, EventType


def _event_prop(value: EventType[()]) -> None: ...


def _event_sequences(
    specs: list[EventSpec], handlers: tuple[EventCallback[()], ...]
) -> None:
    # An event prop takes a list variable of events, not only a list literal,
    # and a tuple of them.
    _event_prop(specs)
    _event_prop(handlers)
