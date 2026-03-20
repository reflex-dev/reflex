"""A registry for all known event handlers."""

import dataclasses
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from reflex.event import EventHandler
    from reflex.state import BaseState


@dataclasses.dataclass(frozen=True, kw_only=True, slots=True)
class RegisteredEventHandler:
    """A registered event handler, which includes the handler and its full name."""

    handler: EventHandler
    states: tuple[type[BaseState], ...]


REGISTERED_HANDLERS: dict[str, RegisteredEventHandler] = {}


def register(handler: EventHandler, states: tuple[type[BaseState], ...] = ()) -> None:
    """Register an event handler with its full name and associated states."""
    from reflex.utils.format import format_event_handler

    REGISTERED_HANDLERS[format_event_handler(handler)] = RegisteredEventHandler(
        handler=handler, states=states
    )
