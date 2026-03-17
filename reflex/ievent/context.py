"""The context and associated metadata for handling an event."""

import dataclasses
import functools
import uuid
from collections.abc import Callable, Mapping
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Protocol

from reflex.istate.manager import StateManager
from reflex.utils.format import to_snake_case

if TYPE_CHECKING:
    from reflex.event import Event


@functools.lru_cache
def get_name(cls: type | Callable) -> str:
    """Get the name of the state/func.

    Returns:
        The name of the state/func.
    """
    module = cls.__module__.replace(".", "___")
    qualname = getattr(cls, "__qualname__", cls.__name__).replace(".", "___")
    return to_snake_case(f"{module}___{qualname}")


class EnqueueProtocol(Protocol):
    """Protocol for the enqueue function in the event context."""

    async def __call__(self, event: Event) -> None:
        """Enqueue an event handler to be executed.

        Args:
            event: The event to enqueue.
        """
        ...


class EmitDeltaProtocol(Protocol):
    """Protocol for the emit_delta function in the event context."""

    async def __call__(
        self,
        deltas: Mapping[str, Mapping[str, Any]],
    ) -> None:
        """Emit a delta to the frontend.

        Args:
            deltas: The deltas to emit, mapping client tokens to variable updates.
        """
        ...


@dataclasses.dataclass(frozen=True, kw_only=True)
class EventContext:
    """The context for an event."""

    # Identifies the client session.
    token: str

    # Manages persistence of state across events.
    state_manager: StateManager

    # Function responsible for enqueuing an event handler to be executed.
    enqueue: EnqueueProtocol

    # Each event is associated with a top-level transaction id.
    txid: str = dataclasses.field(default_factory=lambda: uuid.uuid4().hex[:12])
    # The txid of another EventContext that enqueued this context's event.
    parent_txid: str | None = None

    emit_delta: EmitDeltaProtocol | None = None
    cached_states: dict[type, Any] = dataclasses.field(default_factory=dict, init=False)


event_context: ContextVar[EventContext] = ContextVar("event_context")
