"""Functions for processing BaseState-derived event handlers."""

from __future__ import annotations

import asyncio
import dataclasses
import functools
import inspect
import logging
import warnings
from collections.abc import Mapping, Sequence
from enum import Enum
from importlib.util import find_spec
from time import perf_counter
from typing import TYPE_CHECKING, Any

from reflex.istate.manager.token import BaseStateToken
from reflex.istate.proxy import StateProxy
from reflex.utils import types
from reflex_base import otel
from reflex_base.constants import CompileVars
from reflex_base.event import Event, EventHandler, EventSpec
from reflex_base.event.context import EventContext
from reflex_base.event.processor.event_processor import EventProcessor, EventQueueEntry
from reflex_base.event.processor.future import EventFuture
from reflex_base.registry import RegisteredEventHandler
from reflex_base.utils.form import form_data_as_dict, transform_form_data
from reflex_base.utils.format import format_event_handler
from reflex_base.utils.serializers import deserializers
from reflex_base.utils.types import is_non_string_sequence

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from reflex.state import BaseState, State

# Resolved once at import: find_spec on a missing package scans sys.path (~90us),
# far too slow for the per-event-argument path below.
if find_spec("pydantic"):
    from pydantic import BaseModel as BaseModelV2
else:
    BaseModelV2 = None


@functools.lru_cache(maxsize=1)
def _hydrate_event_names() -> frozenset[str]:
    from reflex.state import State

    return frozenset(
        format_event_handler(State.event_handlers[name])
        for name in (CompileVars.HYDRATE, CompileVars.HYDRATE_AND_LOAD)
    )


@functools.lru_cache(maxsize=1)
def _connect_supersedes() -> tuple[str, str]:
    """The (re)connect event and the page-load event whose chain it cancels.

    Returns:
        The full event names of ``hydrate_and_load`` and ``on_load_internal``.
    """
    from reflex.state import OnLoadInternalState, State

    return (
        format_event_handler(State.event_handlers[CompileVars.HYDRATE_AND_LOAD]),
        format_event_handler(OnLoadInternalState.event_handlers["on_load_internal"]),
    )


_EVENT_LIKE_TYPES = (Event, EventHandler, EventSpec)


def _is_event_like(value: Any) -> bool:
    """Whether a handler's return value is an event or a sequence of events.

    Args:
        value: The value a handler returned or yielded.

    Returns:
        True for an Event, EventHandler or EventSpec, or a sequence of them.
    """
    if isinstance(value, _EVENT_LIKE_TYPES):
        return True
    if not is_non_string_sequence(value):
        return False
    try:
        return all(isinstance(e, _EVENT_LIKE_TYPES) for e in value)
    except TypeError:
        return False


def _contains_events(value: Any) -> bool:
    """Whether a sequence holds at least one event next to other values.

    Args:
        value: The value a handler returned.

    Returns:
        True for a sequence with an event in it that ``_is_event_like`` rejects.
    """
    if not is_non_string_sequence(value):
        return False
    try:
        return any(isinstance(e, _EVENT_LIKE_TYPES) for e in value)
    except TypeError:
        return False


def _check_valid_yield(events: Any, handler_name: str = "unknown") -> Any:
    """Check if the events yielded are valid. They must be EventHandlers or EventSpecs.

    Args:
        events: The events to be checked.
        handler_name: The name of the handler that yielded the events, used for error messages.

    Returns:
        The events as they are if valid.

    Raises:
        TypeError: If any of the events are not valid.
    """
    if events is None or _is_event_like(events):
        return events

    if not is_non_string_sequence(events):
        events = [events]

    coroutines = [e for e in events if inspect.iscoroutine(e)]

    for coroutine in coroutines:
        coroutine_name = coroutine.__qualname__
        warnings.filterwarnings(
            "ignore", message=f"coroutine '{coroutine_name}' was never awaited"
        )

    msg = (
        f"Your handler {handler_name} must only return/yield: None, Events or other EventHandlers referenced by their class (i.e. using `type(self)` or other class references)."
        f" Returned events of types {', '.join(map(str, map(type, events)))!s}."
    )
    raise TypeError(msg)


def _transform_event_arg(value: Any, hinted_args: Any) -> Any:
    """Transform an event argument based on its type hint.

    Args:
        value: The value to transform.
        hinted_args: The type hint for the argument.

    Returns:
        The transformed value.

    Raises:
        ValueError: If a string value is received for an int or float type and cannot be converted.
    """
    value = transform_form_data(value, hinted_args)
    if hinted_args is Any:
        return value
    if types.is_union(hinted_args):
        if value is None:
            return value
        hinted_args = types.value_inside_optional(hinted_args)
    if isinstance(value, dict) and isinstance(hinted_args, type):
        from reflex.model import Model

        if issubclass(hinted_args, Model):
            # Remove non-fields from the payload
            model_fields = hinted_args.model_fields
            return hinted_args(**{
                key: value for key, value in value.items() if key in model_fields
            })
        if dataclasses.is_dataclass(hinted_args):
            return hinted_args(**value)
        if BaseModelV2 is not None and issubclass(hinted_args, BaseModelV2):
            return hinted_args.model_validate(value)
    if isinstance(value, list) and (hinted_args is set or hinted_args is frozenset):
        return set(value)
    if isinstance(value, list) and hinted_args is tuple:
        return tuple(value)
    if isinstance(hinted_args, type) and issubclass(hinted_args, Enum):
        try:
            return hinted_args(value)
        except ValueError:
            msg = f"Received an invalid enum value ({value}) for type {hinted_args}"
            raise ValueError(msg) from None
    if (
        isinstance(value, str)
        and (deserializer := deserializers.get(hinted_args)) is not None
    ):
        try:
            return deserializer(value)
        except ValueError:
            msg = f"Received a string value ({value}) but expected a {hinted_args}"
            raise ValueError(msg) from None
    return value


def _transform_event_payload(
    payload: Mapping[str, Any], type_hints: Mapping[str, Any]
) -> dict[str, Any]:
    """Transform an event payload based on the type hints of the handler.

    Args:
        payload: The event payload to transform.
        type_hints: The type hints for the handler's arguments.

    Returns:
        The transformed event payload.
    """
    transformed = {}
    for arg, value in payload.items():
        hinted_args = type_hints.get(arg, Any)
        try:
            transformed[arg] = _transform_event_arg(value, hinted_args)
        except Exception as ex:
            msg = f"Error transforming event argument '{arg}' with value '{value}' and type hint '{hinted_args}'"
            raise ValueError(msg) from ex
    return transformed


def _prepare_event_payload(
    handler: EventHandler, payload: Mapping[str, Any]
) -> dict[str, Any]:
    """Transform an event payload for a handler's annotations.

    Args:
        handler: The event handler.
        payload: The event payload.

    Returns:
        The transformed payload or, when it cannot be transformed, the original
        payload with any form data as a dict.
    """
    try:
        # Resolved hints are cached on the handler, empty for an unannotated one;
        # fall back for ones that were not resolvable at registration (None),
        # raising again if still unresolved.
        type_hints = handler._type_hints
        if type_hints is None:
            type_hints = types.get_type_hints(handler.fn)
        return _transform_event_payload(payload, type_hints)
    except Exception as ex:
        logger.warning(
            f"Error transforming event payload for handler {handler.fn.__qualname__}: {ex}"
        )
        return {arg: form_data_as_dict(value) for arg, value in payload.items()}


async def _route_events(ctx: EventContext, events: Sequence[Event]) -> None:
    """Emit frontend events to the client and queue backend events.

    Events whose name starts with ``_`` are frontend-only specs (e.g.
    ``_redirect``, ``_call_function``) with no registered backend handler.

    Args:
        ctx: The event context to emit/enqueue through.
        events: The events to route.
    """
    frontend_events: list[Event] = []
    backend_events: list[Event] = []
    for ev in events:
        if ev.name.startswith("_"):
            frontend_events.append(ev)
        else:
            backend_events.append(ev)
    if frontend_events:
        await ctx.emit_event(*frontend_events)
    if backend_events:
        await ctx.enqueue(*backend_events)


async def chain_updates(
    events: Any,
    handler_name: str,
    root_state: BaseState | None = None,
) -> None:
    """Chain yielded events and emit a delta to the frontend.

    Check for validitity and convert the EventSpec into qualified Event objects
    to be queued against the current EventContext.

    Args:
        events: Whatever the handler yielded; `_check_valid_yield` raises TypeError
            for anything that is not an Event, EventHandler, EventSpec, a sequence
            of those, or None.
        handler_name: The name of the handler that yielded the events, used for error messages.
        root_state: The root state of the app, no delta emitted if omitted.
    """
    ctx = EventContext.get()

    if root_state is not None:
        # Emit deltas first, so any frontend events are processed with the
        # latest state. The clean deliberately runs after resolution: the
        # SharedState fan-out captures its dirty vars at clean time, and
        # resolving the delta is what re-marks linked vars through the patch
        # machinery, so cleaning earlier would fan out a stale set (see
        # tests/integration/test_linked_state.py).
        try:
            delta = await root_state._get_resolved_delta()
            if delta:
                await ctx.emit_delta(delta)
        finally:
            root_state._clean()

    # Convert valid EventHandler and EventSpec into Event
    if events is not None and (
        fixed_events := Event.from_event_type(
            _check_valid_yield(events, handler_name=handler_name),
        )
    ):
        await _route_events(ctx, fixed_events)


def ensure_locked(
    state: BaseState | StateProxy | None, root_state: BaseState | None
) -> BaseState | None:
    """The root to flush deltas from, only while the state lock is held.

    Foreground handlers pass the locked root in. A background handler
    yielding from inside ``async with self`` is suspended while its proxy
    still holds the lock, so flushing through the proxy's root keeps the
    documented ordering: deltas reach the frontend before the yielded event.
    Outside the proxy context there is no lock, and flushing there is the
    unlocked snapshot/clean that discards concurrent writes. Evaluated per
    yield: a generator can move between inside and outside the context.

    Args:
        state: The state the handler runs against, possibly a StateProxy.
        root_state: The locked root passed by foreground callers, if any.

    Returns:
        The root state to flush, or None when the lock is not held.
    """
    if root_state is not None:
        return root_state
    if isinstance(state, StateProxy) and state._is_mutable():
        return state.__wrapped__._get_root_state()
    return None


async def execute_event_inline(spec: EventSpec) -> Any:
    """Run the event a spec describes from inside the active EventContext.

    This is what awaiting an EventHandler or EventSpec does. While the current
    task holds the token's state lock (a foreground handler, ``async with
    self`` in a background handler, ``app.modify_state``), the handler runs
    inline on the locked state tree under the caller's context: its yields
    emit deltas and the events it yields chain under the caller's event. With
    no lock held, the event is enqueued and its future awaited. A stateless
    handler always runs inline.

    Args:
        spec: The event spec to execute.

    Returns:
        The handler's return value.

    Raises:
        EventHandlerTypeError: If there is no active EventContext, the spec is
            a frontend-only or upload event, or a background handler is
            awaited while the state lock is held (which would deadlock).
    """
    from reflex_base.registry import RegistrationContext
    from reflex_base.utils.exceptions import EventHandlerTypeError

    try:
        ctx = EventContext.get()
    except LookupError as le:
        msg = (
            f"Event handler `{format_event_handler(spec.handler)}` can only be "
            "awaited from an event handler or inside `app.modify_state`; use it "
            "as an event trigger or yield it instead."
        )
        raise EventHandlerTypeError(msg) from le
    event = spec._to_event(ctx.router_data)
    name = event.name
    if spec.client_handler_name:
        msg = f"Upload event `{name}` cannot be awaited; use it as an event trigger."
        raise EventHandlerTypeError(msg)
    registered = RegistrationContext.get().event_handlers.get(name)
    if registered is None:
        msg = (
            f"`{name}` is a frontend-only event, so it cannot be awaited; "
            "yield or return it instead."
        )
        raise EventHandlerTypeError(msg)
    handler = registered.handler
    root_state = ctx.locked_root
    if not registered.states:
        if root_state is None:
            return await process_event(
                handler=handler, payload=event.payload, state=None, root_state=None
            )
    elif root_state is None:
        (future,) = await ctx.enqueue(event)
        return await future
    elif handler.is_background:
        msg = (
            f"Background event handler `{name}` cannot be awaited while the "
            "state lock is held, as it would wait for that lock; yield it instead."
        )
        raise EventHandlerTypeError(msg)
    # Under the lock, a stateless handler flushes the caller's pending delta
    # through the locked root before any frontend event it yields, like every
    # other yield does, so it is covered by the lock like a state handler.
    # The lock stays held until this run is done, even if the task that
    # started it finishes first. Registered before the first await, so a
    # task that starts while the lock is held is always seen by its release.
    # A nested inline run on an already registered task leaves the outer
    # run's registration in place.
    task = asyncio.current_task()
    if task is None or task in ctx.inline_tasks:
        # Nothing to register here, and nothing to unregister after.
        task = None
    else:
        ctx.inline_tasks.add(task)
    try:
        substate = (
            await root_state.get_state(registered.states[0])
            if registered.states
            else None
        )
        return await process_event(
            handler=handler,
            payload=event.payload,
            state=substate,
            root_state=root_state,
        )
    finally:
        if task is not None:
            ctx.inline_tasks.discard(task)


async def process_event(
    handler: EventHandler,
    payload: dict,
    state: BaseState | StateProxy | None,
    root_state: BaseState | None,
) -> Any:
    """Process event.

    Args:
        handler: EventHandler to process.
        payload: The event payload.
        state: State to process the handler, or None for a stateless handler.
        root_state: The root state of the app, used for emitting deltas. Pass
            None when the caller does not hold the state lock (background
            tasks): computing and cleaning a delta on an unlocked root races
            concurrent events on a shared state tree, and background state
            changes are emitted by the ``async with self`` context exits
            instead.

    Returns:
        The handler's return value, None when it returned nothing or events
        (which are chained instead).

    Raises:
        ValueError: If a string value is received for an int or float type and cannot be converted.
    """
    fn = handler.fn
    handler_name = fn.__qualname__
    payload = _prepare_event_payload(handler, payload)

    # A stateless handler takes no state argument.
    args = () if state is None else (state,)
    # Handle async functions.
    if handler._is_coroutine_function:
        events = await fn(*args, **payload)

    # Handle regular functions.
    else:
        events = fn(*args, **payload)
    # Handle async generators.
    if inspect.isasyncgen(events):
        async for event in events:
            await chain_updates(
                event,
                root_state=ensure_locked(state, root_state),
                handler_name=handler_name,
            )
        events = None

    # Handle regular generators.
    elif inspect.isgenerator(events):
        try:
            while True:
                await chain_updates(
                    next(events),
                    root_state=ensure_locked(state, root_state),
                    handler_name=handler_name,
                )
        except StopIteration as si:
            # the "return" value of the generator is not available
            # in the loop, we must catch StopIteration to access it
            events = si.value

    # Chain a returned event (or events); anything else is the result.
    if events is None or _is_event_like(events):
        await chain_updates(
            events,
            root_state=ensure_locked(state, root_state),
            handler_name=handler_name,
        )
        return None
    if inspect.iscoroutine(events) or _contains_events(events):
        # A coroutine that was never awaited, or events mixed with other
        # values, is a bug, not a result.
        _check_valid_yield(events, handler_name=handler_name)
    await chain_updates(
        None, root_state=ensure_locked(state, root_state), handler_name=handler_name
    )
    return events


class BaseStateEventProcessor(EventProcessor):
    """Event processor for BaseState-derived states.

    This processor is used to process events for BaseState-derived states, and
    is responsible for maintaining the event queue and emitting deltas to the
    frontend.
    """

    @staticmethod
    async def _rehydrate_snapshot(root_state: State) -> None:
        """Send hydration data, finishing hydration when no page is available.

        Args:
            root_state: The root state to rehydrate.
        """
        from reflex.state import State

        routeless = not root_state.router_data
        if routeless and root_state.is_hydrated:
            return
        await process_event(
            handler=State.event_handlers["hydrate"],
            payload={},
            state=root_state,
            root_state=root_state,
        )
        if routeless:
            await process_event(
                handler=State.event_handlers["set_is_hydrated"],
                payload={"value": True},
                state=root_state,
                root_state=root_state,
            )

    @functools.cached_property
    def _pending_hydrates(self) -> dict[str, dict[str, EventFuture]]:
        """Hydrations cancellable on disconnect, but never by a navigation.

        Returns:
            Pending hydration futures indexed by client token and transaction id.
        """
        return {}

    async def _rehydrate(self, root_state: BaseState):
        """Rehydrate the state by calling the hydrate event handler.

        Args:
            root_state: The root state to rehydrate.
        """
        from reflex.event import Event
        from reflex.state import OnLoadInternalState, State

        if type(root_state) is not State:
            return

        # A backend-initiated event carries no route, so nothing sets
        # router_data and every one of them would rehydrate again.
        if not root_state.router_data:
            await self._rehydrate_snapshot(root_state)
            return

        ctx = EventContext.get()
        # Disconnect cancels this marker without cancelling the ordinary event.
        pending = EventFuture(txid=ctx.txid)
        self._pending_hydrates.setdefault(ctx.token, {})[pending.txid] = pending
        try:
            await self._rehydrate_snapshot(root_state)
            if pending.cancelled():
                return
            parent = self._futures[ctx.txid]
            first_child = len(parent.children)
            handler = OnLoadInternalState.event_handlers["on_load_internal"]
            await process_event(
                handler=handler,
                payload={},
                state=await root_state.get_state(OnLoadInternalState),
                root_state=root_state,
            )
            # Inline rehydration bypasses enqueue's page-load registration. Track
            # only its children so the ordinary event remains independent.
            load_event = Event(name=format_event_handler(handler))
            for index in range(first_child, len(parent.children)):
                child = parent.children[index]
                if pending.cancelled():
                    child.cancel()
                else:
                    self._supersede_previous(
                        token=ctx.token, event=load_event, tracked=child
                    )
        finally:
            self._forget_hydrate(ctx.token, pending)

    def _supersede_previous(
        self, *, token: str, event: Event, tracked: EventFuture
    ) -> bool:
        """Apply supersession, with a (re)connect obsoleting the pending page load.

        Enqueuing ``hydrate_and_load`` cancels the token's unfinished
        ``on_load_internal`` chain the way a navigation does, before the
        hydrate waits for the state lock that chain may hold. The hydrate is
        not registered as superseding itself: a navigation enqueued while it
        waits must not cancel the state snapshot it is about to send.

        Args:
            token: The client token associated with the event.
            event: The event being enqueued.
            tracked: The future of the event being enqueued.

        Returns:
            True if the event should be queued, False if it was dropped.
        """
        boot_name, on_load_name = _connect_supersedes()
        if event.name == boot_name:
            self._cancel_older_chains((on_load_name, token), tracked.root_gen)
            self._pending_hydrates.setdefault(token, {})[tracked.txid] = tracked
            tracked.add_done_callback(functools.partial(self._forget_hydrate, token))
        return super()._supersede_previous(token=token, event=event, tracked=tracked)

    def _forget_hydrate(self, token: str, future: EventFuture) -> None:
        """Stop tracking a completed hydration invocation.

        Its page-load descendants have their own supersession registration.

        Args:
            token: The client token.
            future: The completed hydration future.
        """
        if (pending := self._pending_hydrates.get(token)) is not None:
            pending.pop(future.txid, None)
            if not pending:
                del self._pending_hydrates[token]

    def _on_disconnect(self, token: str) -> None:
        """Cancel hydration and unfinished page-load chains for a disconnected client.

        Args:
            token: The disconnected client token.
        """
        _, on_load_name = _connect_supersedes()
        for future in self._pending_hydrates.pop(token, {}).values():
            future.cancel()
        for future in self._superseded.pop((on_load_name, token), {}).values():
            future.cancel()

    def _runs_unordered(self, registered_handler: RegisteredEventHandler) -> bool:
        """Whether an event runs immediately instead of in its token's FIFO.

        The FIFO serializes the handlers that take the token's state lock. A
        stateless handler takes none, so it runs like a background one.

        Args:
            registered_handler: The registered handler for the event.

        Returns:
            True for a background or stateless handler.
        """
        return registered_handler.handler.is_background or not registered_handler.states

    async def _execute_event(
        self, *, entry: EventQueueEntry, registered_handler: RegisteredEventHandler
    ) -> Any:
        """Execute the handler for a single event queue entry with full state management.

        The ``EventContext`` has already been set by ``_process_event_queue_entry``
        before this method is called.

        Args:
            entry: The event queue entry to process.
            registered_handler: The registered handler for the event.

        Returns:
            The handler's return value, which resolves the event's future.
        """
        ctx = entry.ctx
        event = entry.event
        if not registered_handler.states:
            # A stateless handler holds no lock and gets no state.
            return await process_event(
                handler=registered_handler.handler,
                payload=event.payload,
                state=None,
                root_state=None,
            )
        # The context, not the event: a chained event carries none of its own
        # and inherits the producing view's through fork().
        router_data = ctx.router_data
        acquire_start = perf_counter() if otel.enabled else 0.0
        # Get the state for the session exclusively.
        async with ctx.state_manager.modify_state_with_links(
            BaseStateToken(
                ident=ctx.token,
                cls=registered_handler.states[0],
            ),
            event=entry.event,
        ) as state:
            if otel.enabled:
                otel.record_state_acquired(acquire_start, event)
            previous_router_data = state.router_data
            # Compatibility hack rehydrate the state before processing this event.
            needs_to_rehydrate = bool(
                not previous_router_data and event.name not in _hydrate_event_names()
            )

            # re-assign only when the value is set and different
            if router_data and previous_router_data != router_data:
                # only the router vars whose backing keys changed are rebuilt
                # and re-sent; session/headers stay put across navigations.
                merged_router_data = state._update_router_vars(
                    router_data, previous_router_data
                )
                # Store what it merged, not the payload, so a partial payload
                # does not drop the keys it omits. Only on a real change: the
                # assignment dirties router_data and marks the state touched.
                if merged_router_data != previous_router_data:
                    state.router_data = merged_router_data

            # Preprocess the event.
            if (
                self.middleware is not None
                and (update := await self.middleware._preprocess(state, event))
                is not None
            ):
                # If there was an update, yield it.
                if update.delta:
                    await ctx.emit_delta(update.delta)
                if update.events:
                    await _route_events(ctx, update.events)
                return None

            # Get the event's substate.
            substate = await state.get_state(registered_handler.states[0])
            root_state = state._get_root_state()

            # Not `holding_lock`: this is the hot path of every event, and
            # the plain try/finally spares the context manager's overhead.
            ctx.set_locked_root(root_state)
            try:
                if needs_to_rehydrate:
                    await self._rehydrate(root_state)

                # Process non-background events while holding the lock.
                if not registered_handler.handler.is_background:
                    return await process_event(
                        handler=registered_handler.handler,
                        payload=event.payload,
                        state=substate,
                        root_state=root_state,
                    )
            finally:
                await ctx.release_lock()
        # Otherwise drop the state lock and start processing the background task
        # with a proxy state. No root_state: the lock is no longer held, and
        # under a shared state tree (opportunistic locking, in-memory manager)
        # computing a delta here races whatever event holds the lock now -- a
        # foreground write landing between this task's dirty-var snapshot and
        # its _clean() would be discarded before any delta carries it. A
        # background task's own state changes are emitted (and cleaned) by its
        # `async with self` context exits, which re-acquire the lock.
        proxy = StateProxy(substate)
        # Leave the tree loaded under the lock to the proxy, which replaces it on
        # `async with self`. A manager like redis loads a fresh tree for every
        # lock, so these locals would pin an extra copy for the whole task.
        del state, substate, root_state
        handler_error: BaseException | None = None
        result = None
        try:
            result = await process_event(
                handler=registered_handler.handler,
                state=proxy,
                payload=event.payload,
                root_state=None,
            )
        except BaseException as ex:
            handler_error = ex
            raise
        finally:
            if not proxy._self_entered_context:
                # A handler that never entered `async with self` emitted nothing,
                # but every background event used to flush a delta (refreshing
                # uncached computed vars, and any dirty vars the preamble left,
                # like router_data). Preserve that, under the lock this time --
                # also when the handler raises, so the client gets the same
                # refresh regardless of how the task ended.
                try:
                    async with ctx.state_manager.modify_state_with_links(
                        BaseStateToken(
                            ident=ctx.token,
                            cls=registered_handler.states[0],
                        ),
                        event=event,
                    ) as flush_state:
                        await chain_updates(
                            None,
                            root_state=flush_state._get_root_state(),
                            handler_name=registered_handler.handler.fn.__qualname__,
                        )
                except Exception:
                    if handler_error is None:
                        raise
                    # The handler's exception is the actionable one; log the
                    # flush failure instead of letting it mask the exception
                    # already propagating to the backend exception handler.
                    logger.exception(
                        "Error flushing delta after background handler "
                        f"{registered_handler.handler.fn.__qualname__} raised:"
                    )
        return result

    async def _handle_backend_exception(
        self, ex: Exception, ev_ctx: EventContext | None = None
    ) -> None:
        """Handle an exception raised during event processing by calling the backend exception handler if it exists.

        Args:
            ex: The exception that was raised.
            ev_ctx: The event context for the exception.
        """
        if self.backend_exception_handler is not None:
            if ev_ctx is not None:
                # Ensure the event context is set for the exception handler.
                EventContext.set(ev_ctx)
                if otel.enabled:
                    # Chain the handler's events under the failed event's span.
                    otel.attach_context(ev_ctx.otel_context)
            if events := self.backend_exception_handler(ex):
                await chain_updates(
                    events=events,
                    handler_name=self.backend_exception_handler.__qualname__,
                )


__all__ = [
    "BaseStateEventProcessor",
    "chain_updates",
    "execute_event_inline",
    "process_event",
]
