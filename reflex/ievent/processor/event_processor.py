"""Base EventProcessor class for handling backend event queue."""

import asyncio
import dataclasses
import time
import traceback
from collections.abc import Callable, Mapping
from contextvars import Context, copy_context
from typing import TYPE_CHECKING, Any, Self

import rich.markup

from reflex.app_mixins.middleware import MiddlewareMixin
from reflex.ievent.context import EmitDeltaProtocol, EventContext, event_context
from reflex.ievent.processor import base_state_processor
from reflex.ievent.registry import REGISTERED_HANDLERS, RegisteredEventHandler
from reflex.istate.data import RouterData
from reflex.istate.manager import StateManager
from reflex.istate.proxy import StateProxy
from reflex.utils import console
from reflex.utils.tasks import ensure_task

if TYPE_CHECKING:
    from reflex.app import EventNamespace
    from reflex.event import Event, EventSpec


@dataclasses.dataclass(frozen=True, kw_only=True, slots=True)
class EventQueueEntry:
    """An entry in the event queue."""

    event: Event
    ctx: EventContext


@dataclasses.dataclass(kw_only=True, slots=True)
class EventProcessor:
    """Responsible for queuing and processing events."""

    middleware: MiddlewareMixin | None = None
    backend_exception_handler: (
        Callable[[Exception], EventSpec | list[EventSpec] | None] | None
    ) = None

    _queue: asyncio.Queue[EventQueueEntry] = dataclasses.field(
        default_factory=asyncio.Queue, init=False
    )
    _queue_task: asyncio.Task | None = dataclasses.field(default=None, init=False)
    _root_context: Context | None = dataclasses.field(default=None, init=False)
    _tasks: dict[str, asyncio.Task] = dataclasses.field(
        default_factory=dict, init=False
    )

    def configure(
        self,
        state_manager: StateManager | None = None,
        event_namespace: EventNamespace | None = None,
    ) -> Self:
        """Set up the event processor.

        Before an event processor can be used, it must be configured with a
        state manager and optionally an event namespace to communicate with the
        frontend.

        Args:
            state_manager: The state manager to use for processing events.
            event_namespace: The event namespace to use for processing events.

        Returns:
            The event processor instance.
        """
        from reflex.istate.manager.memory import StateManagerMemory
        from reflex.state import StateUpdate

        if self._root_context is not None:
            msg = "Event processor is already running"
            raise RuntimeError(msg)

        emit_delta: EmitDeltaProtocol | None = None
        if event_namespace is not None:

            async def _emit_delta(
                token: str, delta: Mapping[str, Mapping[str, Any]]
            ) -> None:
                """Emit a delta to the frontend.

                Args:
                    token: The client token to emit the delta to.
                    delta: The delta to emit, mapping client tokens to variable updates.
                """
                await event_namespace.emit_update(
                    update=StateUpdate(delta=delta, final=True),
                    token=token,
                )

            emit_delta = _emit_delta

            async def enqueue(token: str, *events: Event) -> None:
                """Enqueue an event handler to be executed.

                Args:
                    token: The client token associated with the event.
                    events: The events to enqueue.
                """
                for event in events:
                    if event.name.startswith("_"):
                        # Frontend events that start with "_" are emitted directly.
                        await event_namespace.emit_update(
                            update=StateUpdate(events=[event]),
                            token=token,
                        )
                    else:
                        # Backend events will be processed by the internal queue.
                        await self.enqueue(token=token, event=event)

        else:

            async def enqueue(token: str, *events: Event) -> None:
                """Enqueue an event handler to be executed.

                Args:
                    token: The client token associated with the event.
                    events: The events to enqueue.
                """
                for event in events:
                    await self.enqueue(token=token, event=event)

        if state_manager is None:
            # For testing use cases, default to a new in-memory state manager if one is not provided.
            state_manager = StateManagerMemory()

        event_context.set(
            EventContext(
                token="",
                parent_txid=None,
                state_manager=state_manager,
                enqueue_impl=enqueue,
                emit_delta_impl=emit_delta,
            ),
        )
        self._root_context = copy_context()
        return self

    async def __aenter__(self) -> "EventProcessor":
        """Enter the event processor context manager.

        Returns:
            The event processor instance.
        """
        self._ensure_queue_task()
        return self

    async def __aexit__(self, *exc_info) -> None:
        """Exit the event processor context manager and stop the processor."""
        await self.stop()

    async def stop(self):
        """Stop the event processor and cancel all running tasks."""
        from reflex.utils import telemetry

        if self._root_context is None:
            msg = "Event processor is not running"
            raise RuntimeError(msg)
        # Cancel the queue processing task.
        if self._queue_task is not None:
            self._queue_task.cancel()
        # Cancel all running event handler tasks.
        for task in self._tasks.values():
            task.cancel()
        # Warn for any non CancelledError exceptions that were raised in the tasks.
        for task in self._tasks.copy().values():
            try:
                await task
            except asyncio.CancelledError:  # noqa: PERF203
                pass
            except Exception as ex:
                telemetry.send_error(ex, context="backend")
                if self.backend_exception_handler is not None:
                    try:
                        await self._handle_backend_exception(
                            ex, ctx=task.get_context().run(event_context.get)
                        )
                    except Exception:
                        console.error(
                            rich.markup.escape(
                                f"Error in backend exception handler for {task.get_name()} during shutdown:\n{traceback.format_exc()}"
                            )
                        )
                    else:
                        return
                console.error(
                    rich.markup.escape(
                        f"Error in event handler task {task.get_name()} during shutdown:\n{traceback.format_exc()}"
                    )
                )

    def _ensure_queue_task(self) -> None:
        """Ensure the queue processing task is running."""
        if self._root_context is None:
            msg = "Event processor is not running, call .start(...) first."
            raise RuntimeError(msg)
        ensure_task(
            self,
            "_queue_task",
            self._process_queue,
            task_context=self._root_context,
        )

    async def enqueue(
        self, token: str, event: Event, ev_ctx: EventContext | None = None
    ) -> None:
        """Enqueue an event to be processed.

        Args:
            token: The client token associated with the event.
            event: The event to enqueue.
            ev_ctx: The event context to use for this event.
        """
        self._ensure_queue_task()
        if ev_ctx is None:
            try:
                ev_ctx = event_context.get().fork(token=token)
            except LookupError as le:
                if self._root_context is not None:
                    ev_ctx = self._root_context.run(event_context.get).fork(token=token)
                else:
                    msg = "Event processor is not running, call .start(...) first."
                    raise RuntimeError(msg) from le
        await self._queue.put(EventQueueEntry(event=event, ctx=ev_ctx))

    async def _process_event_queue_entry(
        self, entry: EventQueueEntry, registered_handler: RegisteredEventHandler
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
            entry.event.substate_token, event=entry.event
        ) as state:
            # TODO: handle "reload" trigger of brand new state instances

            # re-assign only when the value is set and different
            if router_data and state.router_data != router_data:
                # assignment will recurse into substates and force recalculation of
                # dependent ComputedVar (dynamic route variables)
                state.router_data = router_data
                state.router = RouterData.from_router_data(router_data)

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
            substate = await state.get_state(event.substate_token.cls)
            root_state = state._get_root_state()

            # Process non-background events while holding the lock.
            if not registered_handler.handler.is_background:
                await base_state_processor.process_event(
                    handler=registered_handler.handler,
                    payload=event.payload,
                    state=substate,
                    root_state=root_state,
                )
                return
        # Otherwise drop the state lock and start processing the background task with a proxy state.
        await base_state_processor.process_event(
            handler=registered_handler.handler,
            state=StateProxy(substate),
            payload=event.payload,
            root_state=root_state,
        )

    async def _process_queue(self):
        """Process events from the queue in a task."""
        while True:
            entry = await self._queue.get()
            try:
                try:
                    registered_handler = REGISTERED_HANDLERS[entry.event.name]
                except KeyError as ke:
                    msg = f"No registered handler found for event: {entry.event.name}"
                    raise KeyError(msg) from ke
                # Create a new task to handle this event.
                task = asyncio.create_task(
                    self._process_event_queue_entry(entry, registered_handler),
                    name=(
                        f"reflex_event|{entry.event.name}|{entry.ctx.token}|{time.time()}"
                    ),
                )
                self._tasks[entry.ctx.txid] = task
                task.add_done_callback(self._finish_task)
            except Exception:
                # Log the error and continue processing the next events.
                console.error(
                    rich.markup.escape(
                        f"Error processing event queue entry for {entry.event} [txid={entry.ctx.txid}]:\n{traceback.format_exc()}"
                    )
                )

    async def _handle_backend_exception(self, ex: Exception, ctx: EventContext):
        """Handle an exception raised during event processing by calling the backend exception handler if it exists.

        Args:
            ex: The exception that was raised.
            ctx: The event context for the event that caused the exception.
        """
        if self.backend_exception_handler is not None and (
            events := self.backend_exception_handler(ex)
        ):
            await base_state_processor.chain_updates(
                events=events,
                handler_name=self.backend_exception_handler.__qualname__,
            )

    def _finish_task(self, task: asyncio.Task):
        """Callback for finishing a _process_event_queue_entry task.

        This function is responsible for calling the backend exception handler
        if the task raised an exception, and logging any errors that occur
        during the process.

        Args:
            task: The task that finished.
        """
        from reflex.utils import telemetry

        task_ctx = task.get_context().run(event_context.get)
        self._tasks.pop(task_ctx.txid, None)
        if task.done():
            try:
                task.result()
            except asyncio.CancelledError:
                pass
            except Exception as ex:
                telemetry.send_error(ex, context="backend")
                if (
                    not task.get_name().startswith("reflex_backend_exception_handler|")
                    and self.backend_exception_handler is not None
                ):
                    # Create a new task in the same context to invoke the exception handler.
                    t = self._tasks[task_ctx.txid] = task.get_context().run(
                        asyncio.create_task,
                        self._handle_backend_exception(ex, task_ctx),
                        name=f"reflex_backend_exception_handler|task=[{task.get_name()}]|{time.time()}",
                    )
                    t.add_done_callback(self._finish_task)
                    return
                console.error(
                    rich.markup.escape(
                        f"Error in {task.get_name()} [txid={task_ctx.txid}]:\n{traceback.format_exc()}"
                    )
                )


__all__ = [
    "EventProcessor",
    "EventQueueEntry",
]
