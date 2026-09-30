"""The context and associated metadata for handling an event."""

from __future__ import annotations

import dataclasses
import functools
import uuid
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any, Protocol

from reflex_base import otel
from reflex_base.context.base import BaseContext
from reflex_base.environment import environment
from reflex_base.session import SessionToken
from reflex_base.utils import console
from reflex_base.utils.compat import MISSING_TYPE
from reflex_base.utils.exceptions import SessionAuthorizationError
from reflex_base.utils.format import to_snake_case

if TYPE_CHECKING:
    from opentelemetry.context import Context

    from reflex.istate.manager import StateManager
    from reflex_base.event import Event


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

    async def __call__(self, token: str, *events: Event) -> Any:
        """Enqueue an event handler to be executed.

        Args:
            token: The client token associated with the event.
            events: The events to enqueue.
        """
        ...


class EmitEventProtocol(Protocol):
    """Protocol for the emit_event function in the event context."""

    async def __call__(self, token: str, *events: Event) -> Any:
        """Emit an event to be processed immediately.

        Args:
            token: The client token associated with the event.
            events: The events to emit.
        """
        ...


class EmitDeltaProtocol(Protocol):
    """Protocol for the emit_delta function in the event context."""

    async def __call__(
        self,
        token: str,
        delta: Mapping[str, Mapping[str, Any]],
    ) -> Any:
        """Emit a delta to the frontend.

        Args:
            token: The client token to emit the delta to.
            delta: The deltas to emit, mapping client tokens to variable updates.
        """
        ...


@dataclasses.dataclass(frozen=True, kw_only=True, slots=True, eq=False)
class EventContext(BaseContext):
    """The context for an event."""

    # Identifies the client session.
    token: str

    # Validated browser session, or SYSTEM for trusted server-side work.
    session_token: SessionToken | None = dataclasses.field(default=None, repr=False)

    # Manages persistence of state across events.
    state_manager: StateManager = dataclasses.field(repr=False)

    # Function responsible for enqueuing an event handler to be executed.
    enqueue_impl: EnqueueProtocol = dataclasses.field(repr=False)

    # Each event is associated with a top-level transaction id.
    txid: str = dataclasses.field(default_factory=lambda: uuid.uuid4().hex[:12])
    # The txid of another EventContext that enqueued this context's event.
    parent_txid: str | None = None

    emit_delta_impl: EmitDeltaProtocol | None = dataclasses.field(
        default=None, repr=False
    )
    emit_event_impl: EmitEventProtocol | None = dataclasses.field(
        default=None, repr=False
    )
    cached_states: dict[type, Any] = dataclasses.field(
        default_factory=dict, init=False, repr=False
    )
    # OpenTelemetry context active when this event was enqueued (None when tracing is off).
    otel_context: Context | None = dataclasses.field(default=None, repr=False)

    # Routing data of the event being processed. Inherited by fork(), so an
    # event a handler yields resolves against the view that produced it.
    router_data: dict[str, Any] = dataclasses.field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        """Validate the requested client state against the session.

        Raises:
            SessionAuthorizationError: If enforcement rejects the client token.
        """
        if not self.token or (
            self.session_token is not None and self.session_token.authorizes(self.token)
        ):
            return
        mode = environment.REFLEX_SESSION_TOKEN_MODE.get()
        if mode == "off":
            return
        if mode == "enforce":
            msg = "The session does not authorize this client token."
            raise SessionAuthorizationError(msg)
        console.deprecate(
            feature_name="State access without an authorized session",
            reason=(
                "Pass the requesting session when accessing client state. "
                "Trusted server-side work may explicitly use SessionToken.SYSTEM. "
                "REFLEX_SESSION_TOKEN_MODE=enforce rejects this access."
            ),
            deprecation_version="0.9.13",
            removal_version="1.0",
        )

    def fork(
        self,
        token: str | None = None,
        *,
        session_token: SessionToken | MISSING_TYPE | None = dataclasses.MISSING,
    ) -> EventContext:
        """Return a new EventContext with the specified fields replaced.

        Args:
            token: The client token for the new context.
            session_token: The session to use, or omitted to inherit this context's session.

        Returns:
            A new EventContext with the specified fields replaced.
        """
        return type(self)(
            token=self.token if token is None else token,
            session_token=self.session_token
            if session_token is dataclasses.MISSING
            else session_token,
            parent_txid=self.txid,
            state_manager=self.state_manager,
            enqueue_impl=self.enqueue_impl,
            emit_delta_impl=self.emit_delta_impl,
            emit_event_impl=self.emit_event_impl,
            router_data=self.router_data,
            otel_context=otel.capture_context(),
        )

    async def emit_delta(self, delta: Mapping[str, Mapping[str, Any]]) -> None:
        """Emit a delta to the frontend.

        Args:
            delta: The deltas to emit, mapping client tokens to variable updates.
        """
        if self.emit_delta_impl is not None:
            await self.emit_delta_impl(self.token, delta)

    async def emit_event(self, *events: Event) -> None:
        """Emit an event to be processed on the frontend.

        If no such handler exists, the event will not be processed.

        Args:
            events: The events to emit.
        """
        if self.emit_event_impl is not None:
            await self.emit_event_impl(self.token, *events)

    async def enqueue(self, *event: Event) -> None:
        """Enqueue an event handler to be executed.

        Args:
            event: The event to enqueue.
        """
        await self.enqueue_impl(self.token, *event)
