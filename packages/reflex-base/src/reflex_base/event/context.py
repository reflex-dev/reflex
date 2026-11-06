"""The context and associated metadata for handling an event."""

from __future__ import annotations

import asyncio
import dataclasses
import functools
import logging
import os
from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING, Any, Protocol

from reflex_base import otel
from reflex_base.context.base import BaseContext
from reflex_base.utils.format import to_snake_case

if TYPE_CHECKING:
    from opentelemetry.context import Context

    from reflex.istate.manager import StateManager
    from reflex.state import BaseState
    from reflex_base.event import Event
    from reflex_base.event.processor.future import EventFuture


logger = logging.getLogger(__name__)


@functools.lru_cache
def get_name(cls: type | Callable) -> str:
    """Get the name of the state/func.

    Returns:
        The name of the state/func.
    """
    module = cls.__module__.replace(".", "___")
    qualname = getattr(cls, "__qualname__", cls.__name__).replace(".", "___")
    return to_snake_case(f"{module}___{qualname}")


def _new_txid() -> str:
    """Generate a transaction id.

    Returns:
        12 random hex digits, the same 48 random bits as ``uuid4().hex[:12]``.
    """
    return os.urandom(6).hex()


class EnqueueProtocol(Protocol):
    """Protocol for the enqueue function in the event context."""

    async def __call__(self, token: str, *events: Event) -> Sequence[EventFuture]:
        """Enqueue an event handler to be executed.

        Args:
            token: The client token associated with the event.
            events: The events to enqueue.

        Returns:
            One future per event, each resolving to its handler's return value.
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


class EmitResultProtocol(Protocol):
    """Protocol for the emit_result function in the event context."""

    async def __call__(
        self,
        token: str,
        results: Sequence[Mapping[str, Any]],
        delta: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> Any:
        """Emit result records to the frontend, with the delta that precedes them.

        Args:
            token: The client token to emit the records to.
            results: The result records, each keyed by the request id it answers.
            delta: A delta to apply before the records, in the same message.
        """
        ...


@dataclasses.dataclass(frozen=True, kw_only=True, slots=True, eq=False)
class EventContext(BaseContext):
    """The context for an event."""

    # Identifies the client session.
    token: str

    # Manages persistence of state across events.
    state_manager: StateManager = dataclasses.field(repr=False)

    # Function responsible for enqueuing an event handler to be executed.
    enqueue_impl: EnqueueProtocol = dataclasses.field(repr=False)

    # Each event is associated with a top-level transaction id. Empty for a
    # context that belongs to no event, like an event processor's root context.
    txid: str = dataclasses.field(default_factory=_new_txid)
    # The txid of another EventContext that enqueued this context's event, or
    # None for a top-level event.
    parent_txid: str | None = None

    emit_delta_impl: EmitDeltaProtocol | None = dataclasses.field(
        default=None, repr=False
    )
    emit_event_impl: EmitEventProtocol | None = dataclasses.field(
        default=None, repr=False
    )
    emit_result_impl: EmitResultProtocol | None = dataclasses.field(
        default=None, repr=False
    )
    # The id the frontend gave the event it dispatched, so the values its
    # handler yields or returns can be routed back to the caller. Kept apart
    # from txid, which keys processor bookkeeping and must not be chosen by a
    # client. Never inherited by fork(): chained events report nothing.
    request_id: str | None = None
    # Whether the request's completion record was already sent with the
    # handler's final delta, so the event processor does not send another.
    result_sent: bool = dataclasses.field(default=False, init=False, repr=False)
    # The root of the state tree this task holds the token's state lock on,
    # while it does: set by the event processor around a foreground handler,
    # by ``async with self`` in a background handler, and by
    # ``App.modify_state``. An awaited handler runs inline on it; with no lock
    # held, the handler is enqueued instead. Never inherited by fork().
    locked_root: BaseState | None = dataclasses.field(
        default=None, init=False, repr=False
    )
    # The tasks running an awaited handler inline on the locked tree. The
    # lock is released only once they are done, so a task spawned from a
    # handler cannot keep writing to the tree after the lock is gone.
    inline_tasks: set[asyncio.Task] = dataclasses.field(
        default_factory=set, init=False, repr=False
    )
    # OpenTelemetry context active when this event was enqueued (None when tracing is off).
    otel_context: Context | None = dataclasses.field(default=None, repr=False)

    # Routing data of the event being processed. Inherited by fork(), so an
    # event a handler yields resolves against the view that produced it.
    router_data: dict[str, Any] = dataclasses.field(default_factory=dict, repr=False)

    def fork(
        self,
        token: str | None = None,
        router_data: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> EventContext:
        """Return a new EventContext with the specified fields replaced.

        Args:
            token: The client token for the new context.
            router_data: The routing data for the new context, inherited from this context if empty.
            request_id: The frontend's id for the new context's event, if it has one.

        Returns:
            A new EventContext with the specified fields replaced.
        """
        return type(self)(
            token=token or self.token,
            # Forks of a context without a txid are top-level events.
            parent_txid=self.txid or None,
            state_manager=self.state_manager,
            enqueue_impl=self.enqueue_impl,
            emit_delta_impl=self.emit_delta_impl,
            emit_event_impl=self.emit_event_impl,
            emit_result_impl=self.emit_result_impl,
            request_id=request_id,
            router_data=router_data or self.router_data,
            otel_context=otel.capture_context(),
        )

    def mark_result_sent(self) -> None:
        """Record that the request's completion record went out with the final delta."""
        object.__setattr__(self, "result_sent", True)

    def set_locked_root(self, root_state: BaseState | None) -> None:
        """Record the state tree the current task holds the lock on, or None.

        Args:
            root_state: The locked root state, or None once the lock is released.
        """
        object.__setattr__(self, "locked_root", root_state)

    async def release_lock(self) -> None:
        """Wait for the inline handler runs started under the lock, then unmark it.

        A handler run that another task started inline (``asyncio.ensure_future``
        on a handler) still holds references to the locked tree, so the lock
        stays held until it finishes. When the releasing task is being
        cancelled, those runs are cancelled too.
        """
        if not self.inline_tasks:
            # The common case: nothing was started inline.
            self.set_locked_root(None)
            return
        current = asyncio.current_task()
        # A task already being cancelled (the cancellation arrived inside
        # the locked block) is not interrupted again while it waits, so the
        # runs it waits for are cancelled up front.
        cancelling = current is not None and current.cancelling()
        try:
            # Drain until nothing is left: a run may start another while
            # the earlier ones are awaited.
            while pending := [
                t for t in self.inline_tasks if t is not current and not t.done()
            ]:
                if cancelling:
                    for task in pending:
                        task.cancel()
                try:
                    results = await asyncio.gather(*pending, return_exceptions=True)
                except asyncio.CancelledError:
                    for task in pending:
                        task.cancel()
                    raise
                for task, result in zip(pending, results, strict=True):
                    if isinstance(result, BaseException) and not isinstance(
                        result, asyncio.CancelledError
                    ):
                        # Gathering retrieved the exception, so asyncio would
                        # not report it as unretrieved; keep it visible.
                        logger.error(
                            f"Inline event handler task {task.get_name()} failed:",
                            exc_info=result,
                        )
        finally:
            self.set_locked_root(None)

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

    async def emit_result(
        self,
        *records: Mapping[str, Any],
        delta: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        """Emit result records to the frontend, after the delta that precedes them.

        Without a result channel (a context not connected to a frontend), the
        records are dropped and the delta is emitted on its own.

        Args:
            records: The result records, each keyed by the request id it answers.
            delta: A delta to apply before the records, in the same message.
        """
        if self.emit_result_impl is not None:
            await self.emit_result_impl(self.token, records, delta)
        elif delta:
            await self.emit_delta(delta)

    async def enqueue(self, *event: Event) -> Sequence[EventFuture]:
        """Enqueue an event handler to be executed.

        Args:
            event: The event to enqueue.

        Returns:
            One future per event, each resolving to its handler's return value.
        """
        return await self.enqueue_impl(self.token, *event)
