"""Functions for processing BaseState-derived event handlers."""

import dataclasses
import functools
import inspect
import warnings
from collections.abc import Mapping, Sequence
from enum import Enum
from importlib.util import find_spec
from typing import TYPE_CHECKING, Any

from reflex.ievent.context import event_context
from reflex.ievent.processor import EventProcessor
from reflex.ievent.processor.event_processor import (
    EventQueueEntry,
    RegisteredEventHandler,
)
from reflex.istate.data import RouterData
from reflex.istate.manager.token import BaseStateToken
from reflex.istate.proxy import StateProxy
from reflex.utils import console, types
from reflex.utils.monitoring import is_pyleak_enabled, monitor_loopblocks

if TYPE_CHECKING:
    from reflex.event import EventHandler, EventSpec
    from reflex.state import BaseState


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
    from reflex.event import Event, EventHandler, EventSpec

    def _is_valid_type(events: Any) -> bool:
        return isinstance(events, (Event, EventHandler, EventSpec))

    if events is None or _is_valid_type(events):
        return events

    if not (isinstance(events, Sequence) and not isinstance(events, (str, bytes))):
        events = [events]

    try:
        if all(_is_valid_type(e) for e in events):
            return events
    except TypeError:
        pass

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
    from reflex.model import Model
    from reflex.utils.serializers import deserializers

    if hinted_args is Any:
        return value
    if types.is_union(hinted_args):
        if value is None:
            return value
        hinted_args = types.value_inside_optional(hinted_args)
    if (
        isinstance(value, dict)
        and isinstance(hinted_args, type)
        and not types.is_generic_alias(hinted_args)  # py3.10
    ):
        if issubclass(hinted_args, Model):
            # Remove non-fields from the payload
            return hinted_args(**{
                key: value
                for key, value in value.items()
                if key in hinted_args.__fields__
            })
        if dataclasses.is_dataclass(hinted_args):
            return hinted_args(**value)
        if find_spec("pydantic"):
            from pydantic import BaseModel as BaseModelV2
            from pydantic.v1 import BaseModel as BaseModelV1

            if issubclass(hinted_args, BaseModelV1):
                return hinted_args.parse_obj(value)
            if issubclass(hinted_args, BaseModelV2):
                return hinted_args.model_validate(value)
    if isinstance(value, list) and (hinted_args is set or hinted_args is set):
        return set(value)
    if isinstance(value, list) and (hinted_args is tuple or hinted_args is tuple):
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
    for arg, value in list(payload.items()):
        hinted_args = type_hints.get(arg, Any)
        try:
            transformed[arg] = _transform_event_arg(value, hinted_args)
        except Exception as ex:
            msg = f"Error transforming event argument '{arg}' with value '{value}' and type hint '{hinted_args}'"
            raise ValueError(msg) from ex
    return transformed


async def chain_updates(
    events: EventSpec | list[EventSpec] | None,
    handler_name: str,
    root_state: BaseState | None = None,
) -> None:
    """Chain yielded events and emit a delta to the frontend.

    Check for validitity and convert the EventSpec into qualified Event objects
    to be queued against the current EventContext.

    Args:
        events: The events to queue with the update.
        handler_name: The name of the handler that yielded the events, used for error messages.
        root_state: The root state of the app, no delta emitted if omitted.
    """
    from reflex.event import fix_events

    ctx = event_context.get()
    token = ctx.token

    # Convert valid EventHandler and EventSpec into Event
    if fixed_events := fix_events(
        _check_valid_yield(events, handler_name=handler_name),
        token,
        router_data=root_state.router_data if root_state else None,
    ):
        # Frontend events.
        if frontend_events := [e for e in fixed_events if e.name.startswith("_")]:
            await ctx.emit_event(*frontend_events)
        # Backend events.
        await ctx.enqueue(*(e for e in fixed_events if not e.name.startswith("_")))

    if root_state is not None:
        # Get the delta after processing the event.
        try:
            delta = await root_state._get_resolved_delta()
            if delta:
                await ctx.emit_delta(delta)
        finally:
            root_state._clean()


async def process_event(
    handler: EventHandler,
    payload: dict,
    state: BaseState | StateProxy,
    root_state: BaseState,
):
    """Process event.

    Args:
        handler: EventHandler to process.
        payload: The event payload.
        state: State to process the handler.
        root_state: The root state of the app, used for emitting deltas.

    Raises:
        ValueError: If a string value is received for an int or float type and cannot be converted.
    """
    handler_name = handler.fn.__qualname__

    # Get the function to process the event.
    if is_pyleak_enabled():
        console.debug(f"Monitoring leaks for handler: {handler_name}")
        fn = functools.partial(monitor_loopblocks(handler.fn), state)
    else:
        fn = functools.partial(handler.fn, state)

    try:
        type_hints = types.get_type_hints(handler.fn)
        payload = _transform_event_payload(payload, type_hints)
    except Exception as ex:
        # No transformation was possible, continue with the original payload
        console.warn(
            f"Error transforming event payload for handler {handler_name}: {ex}"
        )

    # Handle async functions.
    if inspect.iscoroutinefunction(fn.func):
        events = await fn(**payload)

    # Handle regular functions.
    else:
        events = fn(**payload)
    # Handle async generators.
    if inspect.isasyncgen(events):
        async for event in events:
            await chain_updates(event, root_state=root_state, handler_name=handler_name)
        await chain_updates(None, root_state=root_state, handler_name=handler_name)

    # Handle regular generators.
    elif inspect.isgenerator(events):
        try:
            while True:
                await chain_updates(
                    next(events), root_state=root_state, handler_name=handler_name
                )
        except StopIteration as si:
            # the "return" value of the generator is not available
            # in the loop, we must catch StopIteration to access it
            if si.value is not None:
                await chain_updates(
                    si.value, root_state=root_state, handler_name=handler_name
                )
        await chain_updates(None, root_state=root_state, handler_name=handler_name)

    # Handle regular event chains.
    else:
        await chain_updates(events, root_state=root_state, handler_name=handler_name)


class BaseStateEventProcessor(EventProcessor):
    """Event processor for BaseState-derived states.

    This processor is used to process events for BaseState-derived states, and
    is responsible for maintaining the event queue and emitting deltas to the
    frontend.
    """

    async def _process_event_queue_entry(
        self, *, entry: EventQueueEntry, registered_handler: RegisteredEventHandler
    ) -> None:
        """Process a single event queue entry.

        This function runs in a new task for each event.

        Args:
            entry: The event queue entry to process.
            registered_handler: The registered handler for the event.
        """
        # Set up the event context for this task.
        ctx = entry.ctx
        event_context.set(ctx)
        event = entry.event
        router_data = event.router_data or {}
        # Get the state for the session exclusively.
        async with ctx.state_manager.modify_state_with_links(
            BaseStateToken(
                ident=ctx.token,
                cls=registered_handler.states[0],
            ),
            event=entry.event,
        ) as state:
            # TODO: handle "reload" trigger of brand new state instances

            # re-assign only when the value is set and different
            if router_data and state.router_data != router_data:
                # assignment will recurse into substates and force recalculation of
                # dependent ComputedVar (dynamic route variables)
                state.router_data = router_data
                if state.router != (router := RouterData.from_router_data(router_data)):
                    state.router = router

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
                    await ctx.enqueue(*update.events)
                return

            # Get the event's substate.
            substate = await state.get_state(event.state_cls)
            root_state = state._get_root_state()

            # Process non-background events while holding the lock.
            if not registered_handler.handler.is_background:
                await process_event(
                    handler=registered_handler.handler,
                    payload=event.payload,
                    state=substate,
                    root_state=root_state,
                )
                return
        # Otherwise drop the state lock and start processing the background task with a proxy state.
        await process_event(
            handler=registered_handler.handler,
            state=StateProxy(substate),
            payload=event.payload,
            root_state=root_state,
        )

    async def _handle_backend_exception(self, ex: Exception):
        """Handle an exception raised during event processing by calling the backend exception handler if it exists.

        Args:
            ex: The exception that was raised.
        """
        if self.backend_exception_handler is not None and (
            events := self.backend_exception_handler(ex)
        ):
            await chain_updates(
                events=events,
                handler_name=self.backend_exception_handler.__qualname__,
            )


__all__ = ["BaseStateEventProcessor", "chain_updates", "process_event"]
