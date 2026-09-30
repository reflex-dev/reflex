"""The context and associated metadata for handling an event."""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import functools
import sys
import uuid
from collections.abc import AsyncIterator, Callable, Mapping
from typing import TYPE_CHECKING, Any, Protocol, TypeVar

from typing_extensions import Unpack

from reflex_base import otel
from reflex_base.context.base import BaseContext
from reflex_base.utils.format import to_snake_case

if TYPE_CHECKING:
    from opentelemetry.context import Context

    from reflex.istate.manager import StateManager, StateModificationContext
    from reflex.istate.manager.token import StateToken
    from reflex_base.event import Event

T = TypeVar("T")


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


@dataclasses.dataclass(slots=True, eq=False)
class _HeldStateLock:
    """A state manager lock held by an EventContext for one ident, shared by its tasks."""

    # The modification context passed when the lock was acquired.
    context: StateModificationContext
    # How many modify_state blocks of the context are inside the lock.
    users: int = 1
    # The lease returned by the state manager once the lock is acquired.
    lease: Any = None
    # Set once acquiring the lock succeeded or failed.
    ready: asyncio.Event = dataclasses.field(default_factory=asyncio.Event)
    # Whether acquiring the lock failed.
    failed: bool = False
    # Releases the state manager lock.
    exit_stack: contextlib.AsyncExitStack = dataclasses.field(
        default_factory=contextlib.AsyncExitStack
    )
    # The context managers held until the lock is released.
    held_contexts: contextlib.AsyncExitStack = dataclasses.field(
        default_factory=contextlib.AsyncExitStack
    )


@dataclasses.dataclass(frozen=True, kw_only=True, slots=True, eq=False)
class EventContext(BaseContext):
    """The context for an event."""

    # Identifies the client session.
    token: str

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
    # The states checked out by this context, by the str of their token: one
    # instance per state class and ident, which trees are linked from.
    cached_states: dict[str, Any] = dataclasses.field(
        default_factory=dict, init=False, repr=False
    )
    # The tokens of the checked out states, by ident then by the token's str.
    _state_tokens: dict[str, dict[str, StateToken]] = dataclasses.field(
        default_factory=dict, init=False, repr=False
    )
    # The token of each checked out state, by the id of the state.
    _state_tokens_by_id: dict[int, StateToken] = dataclasses.field(
        default_factory=dict, init=False, repr=False
    )
    # The str of the tokens whose required states are all checked out.
    _complete_states: set[str] = dataclasses.field(
        default_factory=set, init=False, repr=False
    )
    # The state manager locks held by this context, by ident.
    _held_state_locks: dict[str, _HeldStateLock] = dataclasses.field(
        default_factory=dict, init=False, repr=False
    )
    # Counts the acquisitions of each ident's lock, to detect a load racing one.
    _state_lock_generations: dict[str, int] = dataclasses.field(
        default_factory=dict, init=False, repr=False
    )
    # OpenTelemetry context active when this event was enqueued (None when tracing is off).
    otel_context: Context | None = dataclasses.field(default=None, repr=False)

    # Routing data of the event being processed. Inherited by fork(), so an
    # event a handler yields resolves against the view that produced it.
    router_data: dict[str, Any] = dataclasses.field(default_factory=dict, repr=False)

    def fork(self, token: str | None = None) -> EventContext:
        """Return a new EventContext with the specified fields replaced.

        Args:
            token: The client token for the new context.

        Returns:
            A new EventContext with the specified fields replaced.
        """
        return type(self)(
            token=token or self.token,
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

    def state_token(self, state: Any) -> StateToken | None:
        """Get the token a state was checked out with in this context.

        Args:
            state: The state instance.

        Returns:
            The token, or None if the state was not checked out in this context.
        """
        return self._state_tokens_by_id.get(id(state))

    def _cache_state(
        self, token: StateToken, state: Any, key: str | None = None
    ) -> None:
        """Check out a state in this context and link it to the ones it relates to.

        Args:
            token: The token of the state.
            state: The state instance.
            key: The str of the token, if already computed.
        """
        if key is None:
            key = str(token)
        self.cached_states[key] = state
        self._state_tokens.setdefault(token.ident, {})[key] = token
        self._state_tokens_by_id[id(state)] = token
        token.link(state, self.cached_states)

    async def get_state(self, token: StateToken[T]) -> T:
        """Get the state for a token, loading it into this context if needed.

        The states the token requires are loaded along with it and linked
        together, so every lookup in this context sees the same instances.

        Args:
            token: The token of the state.

        Returns:
            The state checked out for the token.
        """
        key = str(token)
        if key in self._complete_states:
            return self.cached_states[key]
        ident = token.ident
        required_tokens = token.required_tokens()
        cached_states = self.cached_states
        while missing := {
            required_key: required
            for required in required_tokens
            if (required_key := str(required)) not in cached_states
        }:
            generation = self._state_lock_generations.get(ident)
            states = await self.state_manager.load_states(list(missing.values()))
            if self._state_lock_generations.get(ident) != generation:
                # The lock was acquired while loading: load again under it.
                continue
            for (required_key, required), state in zip(
                missing.items(), states, strict=True
            ):
                # Another task of this context may have checked it out meanwhile.
                if required_key not in cached_states:
                    self._cache_state(required, state, required_key)
            break
        self._complete_states.add(key)
        return self.cached_states[key]

    async def _refresh_states(self, ident: str) -> None:
        """Bring the states checked out for an ident up to date with the stored ones.

        Args:
            ident: The ident whose lock was just acquired.
        """
        if not (tokens := self._state_tokens.get(ident)):
            return
        stored_states = await self.state_manager.load_states(
            list(tokens.values()), create=False
        )
        for (key, token), stored in zip(tokens.items(), stored_states, strict=True):
            state = self.cached_states[key]
            if stored is None or stored is state:
                continue
            if (refreshed := token.refresh(state, stored)) is not state:
                self.cached_states[key] = refreshed
                del self._state_tokens_by_id[id(state)]
                self._state_tokens_by_id[id(refreshed)] = token

    async def _acquire_state_lock(
        self, token: StateToken, context: StateModificationContext
    ) -> _HeldStateLock:
        """Acquire the state manager lock for a token's ident, or join it if already held.

        Every task of the context shares the lock, as they share its states.

        Args:
            token: The token to lock.
            context: The state modification context.

        Returns:
            The held lock.
        """
        ident = token.ident
        while (held := self._held_state_locks.get(ident)) is not None:
            held.users += 1
            if not held.ready.is_set():
                try:
                    await held.ready.wait()
                except BaseException:
                    held.users -= 1
                    raise
            if not held.failed:
                return held
            # Acquiring it failed: try again.
        held = self._held_state_locks[ident] = _HeldStateLock(context=context)
        try:
            held.lease = await held.exit_stack.enter_async_context(
                self.state_manager.lock(token, **context)
            )
            self._state_lock_generations[ident] = (
                self._state_lock_generations.get(ident, 0) + 1
            )
            await self._refresh_states(ident)
        except BaseException:
            held.failed = True
            del self._held_state_locks[ident]
            try:
                await held.exit_stack.aclose()
            finally:
                held.ready.set()
            raise
        held.ready.set()
        return held

    async def _release_state_lock(
        self,
        ident: str,
        held: _HeldStateLock,
        exc_info: tuple[type[BaseException] | None, BaseException | None, Any],
    ) -> None:
        """Leave the state manager lock for an ident, releasing it when the last user leaves.

        Releasing it leaves the context managers held with it, then stores the
        ident's states, unless the last user left with an exception.

        Args:
            ident: The locked ident.
            held: The held lock.
            exc_info: The exception the user left with, if any.
        """
        held.users -= 1
        if held.users:
            return
        del self._held_state_locks[ident]
        async with held.exit_stack:
            await held.held_contexts.__aexit__(*exc_info)
            if exc_info[0] is None and (tokens := self._state_tokens.get(ident)):
                await self.state_manager.store_states(
                    [(token, self.cached_states[key]) for key, token in tokens.items()],
                    held.lease,
                    **held.context,
                )

    async def hold_while_locked(
        self, ident: str, context_manager: contextlib.AbstractAsyncContextManager[T]
    ) -> T:
        """Enter a context manager, leaving it when this context releases an ident's lock.

        Must be called while the lock is held, from a modify_state block.

        Args:
            ident: The locked ident.
            context_manager: The context manager to enter.

        Returns:
            The value the context manager enters with.
        """
        return await self._held_state_locks[ident].held_contexts.enter_async_context(
            context_manager
        )

    @contextlib.asynccontextmanager
    async def modify_state(
        self, token: StateToken[T], **context: Unpack[StateModificationContext]
    ) -> AsyncIterator[T]:
        """Get the state for a token while holding the lock on its ident.

        Acquiring the lock refreshes the states of the ident checked out in
        this context, and releasing it stores them. The tasks of the context
        share the lock, as they share its states: it is released when the last
        of them leaves.

        Args:
            token: The token of the state.
            context: The state modification context.

        Yields:
            The state checked out for the token.
        """
        held = await self._acquire_state_lock(token, context)
        try:
            yield await self.get_state(token)
        except BaseException:
            await self._release_state_lock(token.ident, held, sys.exc_info())
            raise
        await self._release_state_lock(token.ident, held, (None, None, None))
