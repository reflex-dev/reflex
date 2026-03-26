"""Base EventProcessor class for handling backend event queue."""

import asyncio
import contextlib
import dataclasses
import inspect
import time
import traceback
from collections.abc import Callable, Mapping
from contextvars import Token, copy_context
from typing import TYPE_CHECKING, Any, Self

import rich.markup

from reflex._internal.registry import RegisteredEventHandler, RegistrationContext
from reflex.app_mixins.middleware import MiddlewareMixin
from reflex.ievent.context import EventContext
from reflex.istate.manager import StateManager
from reflex.utils import console

if TYPE_CHECKING:
    from reflex.app import EventNamespace
    from reflex.event import Event, EventSpec


@dataclasses.dataclass(kw_only=True, slots=True)
class DrainTimeoutManager:
    """Manages an optional combined timeout over multiple calls.

    Each time the context is entered, yield the remaining time until the
    overall timeout is reached, or 0 if the timeout has already been reached.
    This allows multiple operations to share a single overall timeout, even if
    they are not executed sequentially.
    """

    drain_deadline: float | None = None

    @classmethod
    def with_timeout(cls, timeout: float | None) -> "DrainTimeoutManager":
        """Create a DrainTimeoutManager with a specified timeout.

        Args:
            timeout: The overall amount of time in seconds to wait.

        Returns:
            A DrainTimeoutManager instance with the drain deadline set.
        """
        if timeout is None:
            return cls(drain_deadline=None)
        return cls(drain_deadline=time.time() + timeout)

    def __enter__(self) -> float:
        """Enter the context and yield the remaining time.

        Returns:
            The remaining time in seconds until the overall timeout is reached, or 0 if the timeout
            has already been reached.
        """
        if self.drain_deadline is not None:
            return max(0, self.drain_deadline - time.time())
        return 0

    def __exit__(self, *exc_info) -> None:
        """Exit the context. No cleanup necessary."""


@dataclasses.dataclass(frozen=True, kw_only=True, slots=True)
class EventQueueEntry:
    """An entry in the event queue."""

    event: Event
    ctx: EventContext


@dataclasses.dataclass(kw_only=True, slots=True)
class EventProcessor:
    """Responsible for queuing and processing events.

    Attributes:
        middleware: An optional middleware mixin to apply to all events processed by this processor.
        backend_exception_handler: An optional function to handle exceptions raised during event processing. The function should take an Exception as input and return an EventSpec or list of EventSpecs to be emitted in response, or None to not emit any events.
        graceful_shutdown_timeout: An optional amount of time in seconds to wait for the queue to drain before forcefully cancelling tasks when stopping the processor. If None, the processor will not wait and will cancel tasks immediately.

        _queue: The asyncio queue for events to be processed.
        _queue_task: The task responsible for processing the event queue.
        _root_context: The root event context to use for events enqueued without an explicit context.
        _attached_root_context_token: The context variable token for the attached root context, used to reset the context variable on shutdown.
        _tasks: A mapping of active transaction ids to their corresponding event handler tasks, used for tracking and cancellation on shutdown.
    """

    middleware: MiddlewareMixin | None = None
    backend_exception_handler: (
        Callable[[Exception], EventSpec | list[EventSpec] | None] | None
    ) = None
    graceful_shutdown_timeout: float | None = None

    _queue: asyncio.Queue[EventQueueEntry] | None = dataclasses.field(
        default=None, init=False
    )
    _queue_task: asyncio.Task | None = dataclasses.field(default=None, init=False)
    _root_context: EventContext | None = dataclasses.field(default=None, init=False)
    _attached_root_context_token: Token | None = dataclasses.field(
        default=None, init=False
    )
    _tasks: dict[str, asyncio.Task] = dataclasses.field(
        default_factory=dict, init=False
    )

    def configure(
        self,
        *,
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
            msg = (
                "Event processor is already configured, call .configure(...) only once."
            )
            raise RuntimeError(msg)

        emit_delta_impl = emit_event_impl = None
        if event_namespace is not None:

            async def emit_delta(
                token: str, delta: Mapping[str, Mapping[str, Any]]
            ) -> None:
                """Emit a delta to the frontend.

                Args:
                    token: The client token to emit the delta to.
                    delta: The delta to emit, mapping client tokens to variable updates.
                """
                await event_namespace.emit_update(
                    update=StateUpdate(delta=delta),
                    token=token,
                )

            emit_delta_impl = emit_delta

            async def emit_event(token: str, *events: Event) -> None:
                """Emit an event to be processed on the frontend.

                If no such handler exists, the event will not be processed.

                Args:
                    token: The client token to emit the event to.
                    events: The events to emit.
                """
                await event_namespace.emit_update(
                    update=StateUpdate(events=list(events)),
                    token=token,
                )

            emit_event_impl = emit_event

        if state_manager is None:
            # For testing use cases, default to a new in-memory state manager if one is not provided.
            state_manager = StateManagerMemory()

        self._root_context = EventContext(
            token="",
            parent_txid=None,
            state_manager=state_manager,
            enqueue_impl=self.enqueue,
            emit_delta_impl=emit_delta_impl,
            emit_event_impl=emit_event_impl,
        )
        return self

    async def __aenter__(self) -> Self:
        """Enter the event processor context manager.

        Returns:
            The event processor instance.
        """
        await self.start()
        return self

    async def __aexit__(self, *exc_info) -> None:
        """Exit the event processor context manager and stop the processor."""
        await self.stop()

    async def start(self) -> None:
        """Start the event processor."""
        if self._root_context is None:
            msg = "Event processor is not configured, call .configure(...) first."
            raise RuntimeError(msg)
        if self._queue is not None:
            msg = "Event processor is already started"
            raise RuntimeError(msg)
        if self._attached_root_context_token is not None:
            msg = "EventProcessor context cannot be nested."
            raise RuntimeError(msg)
        self._attached_root_context_token = EventContext.set(self._root_context)
        self._queue = asyncio.Queue()
        self._ensure_queue_task()

    async def _stop_tasks(self, timeout: float | None = None) -> None:
        """Stop all running tasks with an optional drain time.

        Args:
            timeout: An optional amount of time in seconds to wait for the
                queue to drain before cancelling tasks. If None, the processor will
                not wait and will cancel tasks immediately.
        """
        finished_tasks = set()
        # Graceful drain time, wait for tasks to finish and handle any exceptions.
        if timeout is not None and self._tasks:
            with contextlib.suppress(asyncio.TimeoutError):
                async for task in asyncio.as_completed(
                    self._tasks.values(), timeout=timeout
                ):
                    # Exceptions are handled in _finish_task and ignored here.
                    with contextlib.suppress(Exception):
                        await task
                    finished_tasks.add(task)
        # Cancel all outstanding event handler tasks.
        outstanding_tasks = [
            task for task in self._tasks.values() if task not in finished_tasks
        ]
        for task in outstanding_tasks:
            task.cancel()
        # Wait for all tasks to finish and log any exceptions that were raised.
        for task in outstanding_tasks:
            with contextlib.suppress(Exception, asyncio.CancelledError):
                # Exceptions are handled in _finish_task.
                await task

    async def stop(self, graceful_shutdown_timeout: float | None = None) -> None:
        """Stop the event processor and cancel all running tasks.

        Args:
            graceful_shutdown_timeout: An optional amount of time in seconds to wait for the
                queue to drain before cancelling tasks. If None, the processor will
                not wait and will cancel tasks immediately.
        """
        from reflex.utils import telemetry

        if self._attached_root_context_token is not None:
            EventContext.reset(self._attached_root_context_token)
            self._attached_root_context_token = None
        # Optional grace period for tasks to finish before cancellation.
        if graceful_shutdown_timeout is None:
            graceful_shutdown_timeout = self.graceful_shutdown_timeout
        drain_timeout = DrainTimeoutManager.with_timeout(graceful_shutdown_timeout)
        with drain_timeout as remaining_time, contextlib.suppress(asyncio.TimeoutError):
            if remaining_time > 0:
                # Drain the queue first of any pending events.
                await self.join(timeout=remaining_time)
        # Stopping tasks may raise exceptions and chain additional deltas so the queue remains open.
        with drain_timeout as remaining_time, contextlib.suppress(asyncio.TimeoutError):
            await self._stop_tasks(timeout=remaining_time)
        # Cancel queue processing now that all tasks have been cancelled.
        if self._queue is not None:
            self._queue.shutdown()
        with drain_timeout as remaining_time, contextlib.suppress(asyncio.TimeoutError):
            if remaining_time > 0:
                await self.join(timeout=remaining_time)
        with drain_timeout as remaining_time, contextlib.suppress(asyncio.TimeoutError):
            # Stop all tasks again now that the queue is shut down, no additional events can be queued.
            await self._stop_tasks(timeout=remaining_time)
        self._queue = None
        if self._queue_task is not None:
            self._queue_task.cancel()
            try:
                await self._queue_task
            except (asyncio.CancelledError, RuntimeError):
                pass
            except Exception as ex:
                telemetry.send_error(ex, context="backend")
                console.error(
                    rich.markup.escape(
                        f"Error in event processor queue task during shutdown:\n{traceback.format_exc()}"
                    )
                )
            self._queue_task = None

    async def join(self, timeout: float | None = None) -> None:
        """Wait for the event processor to finish processing all events in the queue.

        Args:
            timeout: An optional amount of time in seconds to wait for the queue to
                drain before returning. If None, this method will wait indefinitely
                until the queue is fully drained.
        """
        if self._queue is not None:
            await asyncio.wait_for(self._queue.join(), timeout=timeout)

    def _ensure_queue_task(self) -> asyncio.Queue[EventQueueEntry]:
        """Ensure the queue processing task is running.

        Returns:
            The event queue.

        Raises:
            RuntimeError: If the event processor is not running and no queue is provided.
        """
        if self._root_context is None:
            msg = "Event processor is not configured, call .configure(...) first."
            raise RuntimeError(msg)
        if self._queue is None:
            msg = "Event processor is not running, call .start(...) first."
            raise RuntimeError(msg)
        if self._queue_task is None:
            task_context = copy_context()
            task_context.run(EventContext.set, self._root_context)
            self._queue_task = task_context.run(
                asyncio.create_task,
                self._process_queue(),
                name=f"reflex_event_queue_processor|{time.time()}",
            )
        return self._queue

    async def enqueue(
        self, token: str, *events: Event, ev_ctx: EventContext | None = None
    ) -> None:
        """Enqueue an event to be processed.

        Args:
            token: The client token associated with the event.
            events: Remaining positional args are events to be enqueued.
            ev_ctx: The event context to use for these events.
        """
        if ev_ctx is None:
            try:
                ev_ctx = EventContext.get().fork(token=token)
            except LookupError as le:
                if self._root_context is not None:
                    ev_ctx = self._root_context.fork(token=token)
                else:
                    msg = "Event processor is not running, call .start(...) first."
                    raise RuntimeError(msg) from le
        queue = self._ensure_queue_task()
        for event in events:
            await queue.put(EventQueueEntry(event=event, ctx=ev_ctx))

    async def _process_event_queue_entry(
        self, *, entry: EventQueueEntry, registered_handler: RegisteredEventHandler
    ) -> None:
        """Process a single event queue entry.

        This function runs in a new task for each event.

        The default implementation just calls the registered handler function
        with the event payload as keyword arguments.

        Subclasses, such as BaseStateEventProcessor, can override this function
        to provide additional functionality such as state management, event
        chaining, and delta calculation.

        Args:
            entry: The event queue entry to process.
            registered_handler: The registered handler for the event.
        """
        # Set up the event context for this task.
        ctx = entry.ctx
        EventContext.set(ctx)
        event = entry.event
        result = registered_handler.handler.fn(**event.payload)
        if inspect.isawaitable(result):
            await result

    async def _process_queue(self):
        """Process events from the queue in a task."""
        if (queue := self._queue) is None:
            msg = "Event processor is not running, call .start(...) first."
            raise RuntimeError(msg)
        with contextlib.suppress(asyncio.QueueShutDown):
            while True:
                entry = await queue.get()
                try:
                    try:
                        registered_handler = RegistrationContext.get().event_handlers[
                            entry.event.name
                        ]
                    except KeyError as ke:
                        msg = (
                            f"No registered handler found for event: {entry.event.name}"
                        )
                        raise KeyError(msg) from ke
                    # Create a new task to handle this event.
                    task = asyncio.create_task(
                        self._process_event_queue_entry(
                            entry=entry, registered_handler=registered_handler
                        ),
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
                queue.task_done()
        if self._queue_task is asyncio.current_task():
            self._queue_task = None

    async def _handle_backend_exception(self, ex: Exception):
        """Handle an exception raised during event processing by calling the backend exception handler if it exists.

        Args:
            ex: The exception that was raised.
        """
        if self.backend_exception_handler is not None:
            self.backend_exception_handler(ex)

    def _finish_task(self, task: asyncio.Task):
        """Callback for finishing a _process_event_queue_entry task.

        This function is responsible for calling the backend exception handler
        if the task raised an exception, and logging any errors that occur
        during the process.

        Args:
            task: The task that finished.
        """
        from reflex.utils import telemetry

        task_ctx = task.get_context().run(EventContext.get)
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
                        self._handle_backend_exception(ex),
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
