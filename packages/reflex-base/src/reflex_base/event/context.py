"""The context and associated metadata for handling an event."""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import functools
import logging
import os
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
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
        self, token: str | None = None, router_data: dict[str, Any] | None = None
    ) -> EventContext:
        """Return a new EventContext with the specified fields replaced.

        Args:
            token: The client token for the new context.
            router_data: The routing data for the new context, inherited from this context if empty.

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
            router_data=router_data or self.router_data,
            otel_context=otel.capture_context(),
        )

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

    @contextlib.asynccontextmanager
    async def holding_lock(self, root_state: BaseState) -> AsyncIterator[None]:
        """Mark the state lock as held for the duration of the block.

        Args:
            root_state: The root of the locked state tree.

        Yields:
            Nothing.
        """
        self.set_locked_root(root_state)
        try:
            yield
        finally:
            await self.release_lock()

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

    async def enqueue(self, *event: Event) -> Sequence[EventFuture]:
        """Enqueue an event handler to be executed.

        Args:
            event: The event to enqueue.

        Returns:
            One future per event, each resolving to its handler's return value.
        """
        return await self.enqueue_impl(self.token, *event)
