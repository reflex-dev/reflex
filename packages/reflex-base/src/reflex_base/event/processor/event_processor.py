"""Base EventProcessor class for handling backend event queue."""

from __future__ import annotations

import asyncio
import collections
import contextlib
import dataclasses
import inspect
import sys
import time
import traceback
from collections.abc import AsyncGenerator, Callable, Coroutine, Mapping, Sequence
from contextvars import Token, copy_context
from typing import TYPE_CHECKING, Any, TypeVar

import rich.markup
from typing_extensions import Self

from reflex.app_mixins.middleware import MiddlewareMixin
from reflex.istate.manager import StateManager
from reflex.utils import console
from reflex_base.event.context import EventContext
from reflex_base.event.processor.compat import as_completed
from reflex_base.event.processor.future import EventFuture
from reflex_base.event.processor.timeout import DrainTimeoutManager
from reflex_base.registry import RegisteredEventHandler, RegistrationContext

if TYPE_CHECKING:
    from reflex.app import EventNamespace
    from reflex.event import Event, EventSpec

if hasattr(asyncio, "QueueShutDown"):

    class QueueShutDown(asyncio.QueueShutDown):  # pyright: ignore[reportRedeclaration]
        """Exception raised when trying to put an item into a shut down queue."""

else:

    class QueueShutDown(Exception):  # noqa: N818
        """Exception raised when trying to put an item into a shut down queue."""


_StreamItemT = TypeVar("_StreamItemT")


async def _stream_queue_until_done(
    queue: asyncio.Queue[_StreamItemT],
    done_when: Coroutine[Any, Any, Any],
) -> AsyncGenerator[_StreamItemT]:
    """Yield items from ``queue`` until ``done_when`` completes.

    Items are yielded in the order they were enqueued. Completion of
    ``done_when`` is signalled through the same queue via a private sentinel,
    so items enqueued before completion are never lost to a race between
    "watcher done" and "item available".

    Args:
        queue: The queue to drain.
        done_when: Coroutine whose completion marks end-of-stream. Wrapped in
            a task owned by this helper and cancelled on exit.

    Yields:
        Each item pulled from the queue, in order.
    """
    end_of_stream: Any = object()
    watcher = asyncio.create_task(done_when)
    watcher.add_done_callback(lambda _: queue.put_nowait(end_of_stream))
    try:
        while True:
            item = await queue.get()
            if item is end_of_stream:
                return
            yield item
    finally:
        watcher.cancel()


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
    _futures: dict[str, EventFuture] = dataclasses.field(
        default_factory=dict, init=False
    )
    _token_queues: dict[
        str,
        collections.deque[tuple[EventQueueEntry, RegisteredEventHandler]],
    ] = dataclasses.field(default_factory=dict, init=False)

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
            enqueue_impl=self.enqueue_many,
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
                async for task in as_completed(self._tasks.values(), timeout=timeout):
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
        queue = self._queue
        if self._queue is not None:
            if sys.version_info >= (3, 13):
                self._queue.shutdown()
            self._queue = None
        with drain_timeout as remaining_time, contextlib.suppress(asyncio.TimeoutError):
            if remaining_time > 0:
                await self.join(timeout=remaining_time, queue=queue)
        with drain_timeout as remaining_time, contextlib.suppress(asyncio.TimeoutError):
            # Stop all tasks again now that the queue is shut down, no additional events can be queued.
            await self._stop_tasks(timeout=remaining_time)
        if self._queue_task is not None:
            self._queue_task.cancel()
            try:
                await self._queue_task
            except (asyncio.CancelledError, QueueShutDown, RuntimeError):
                pass
            except Exception as ex:
                telemetry.send_error(ex, context="backend")
                console.error(
                    rich.markup.escape(
                        f"Error in event processor queue task during shutdown:\n{traceback.format_exc()}"
                    )
                )
            self._queue_task = None
        # Discard any pending per-token queue entries.
        self._token_queues.clear()
        # Cancel any remaining unresolved futures.
        for future in self._futures.values():
            if not future.done():
                future.cancel()
        self._futures.clear()

    async def join(
        self, timeout: float | None = None, queue: asyncio.Queue | None = None
    ) -> None:
        """Wait for the event processor to finish processing all events in the queue.

        Args:
            timeout: An optional amount of time in seconds to wait for the queue to
                drain before returning. If None, this method will wait indefinitely
                until the queue is fully drained.
            queue: An optional queue to wait for instead of the processor's main
                queue. This can be used to wait for a specific queue to drain, such
                as when using a separate queue for testing.
        """
        if queue is None:
            queue = self._queue
        if queue is not None:
            await asyncio.wait_for(queue.join(), timeout=timeout)

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
            raise QueueShutDown(msg)
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
        self, token: str, event: Event, ev_ctx: EventContext | None = None
    ) -> EventFuture:
        """Enqueue an event to be processed.

        Args:
            token: The client token associated with the event.
            event: The event to be enqueued.
            ev_ctx: The event context to use for this event.

        Returns:
            An EventFuture that resolves to the result of the associated task.
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
        txid = ev_ctx.txid
        parent_future = (
            self._futures.get(ev_ctx.parent_txid)
            if ev_ctx.parent_txid is not None
            else None
        )
        tracked = EventFuture(parent=parent_future, txid=txid)
        self._futures[txid] = tracked
        tracked.add_done_callback(self._try_clean_future)
        tracked.add_done_callback(self._on_future_done)
        # If this context has a parent, register as a child of the parent's future.
        if parent_future is not None:
            parent_future.add_child(tracked)
        await queue.put(EventQueueEntry(event=event, ctx=ev_ctx))
        return tracked

    async def enqueue_many(self, token: str, *events: Event) -> Sequence[EventFuture]:
        """Enqueue multiple events to be processed.

        Args:
            token: The client token associated with the events.
            events: Remaining positional args are events to be enqueued.

        Returns:
            A list of EventFutures corresponding to each enqueued event.
        """
        return [await self.enqueue(token, event) for event in events]

    async def enqueue_stream_delta(
        self,
        token: str,
        event: Event,
    ) -> AsyncGenerator[Mapping[str, Any]]:
        """Enqueue an event to be processed and yield deltas emitted by the event handler.

        Events queued by this method will not emit deltas to their target token in the typical way, instead
        they will be yielded from this generator until the event handler finishes processing.
        Deltas emitted for other tokens will be handled normally.

        Any frontend events or chained events are handled normally and deltas from chained events
        will not be yielded by this method.

        If the consumer stops iterating early, the in-flight event future is
        cancelled so the handler chain does not continue running in the
        background.

        Args:
            token: The client token associated with the event.
            event: The event to be enqueued.

        Yields:
            Deltas emitted by the event handler for the specified token.
        """
        if self._root_context is None:
            msg = "Event processor is not configured, call .configure(...) first."
            raise RuntimeError(msg)

        deltas = asyncio.Queue()

        async def _emit_delta_impl(
            delta_token: str, delta: Mapping[str, Mapping[str, Any]]
        ) -> None:
            if (
                delta_token != token
                and self._root_context is not None
                and self._root_context.emit_delta_impl is not None
            ):
                # Emit deltas for other tokens normally.
                await self._root_context.emit_delta_impl(delta_token, delta)
                return
            await deltas.put(delta)

        task_future = await self.enqueue(
            token,
            event,
            ev_ctx=dataclasses.replace(
                self._root_context,
                token=token,
                emit_delta_impl=_emit_delta_impl,
            ),
        )

        try:
            async for delta in _stream_queue_until_done(
                queue=deltas, done_when=task_future.wait_all()
            ):
                yield delta
        finally:
            # Cancel the event chain if the streaming consumer exits early.
            if not task_future.done():
                task_future.cancel()
        # Raise any exceptions for the caller, waiting for all chained events.
        await task_future.wait_all()

    def _try_clean_future(self, future: EventFuture) -> None:  # type: ignore[override]
        """Pop a future from _futures when it and all immediate children are done.

        After popping, cascade the check upward: if the parent future is also
        done and all its immediate children are done, pop the parent as well.

        This keeps parent futures alive in ``_futures`` while any child still
        needs them for ``wait_all`` and cleanup.

        Args:
            future: The EventFuture to check.
        """
        if not future.done():
            return
        # Not checking future.all_done() to avoid waiting for grandchildren here.
        if not all(c.done() for c in future.children):
            return
        parent = future.parent
        self._futures.pop(future.txid, None)
        if parent is not None and parent.txid:
            self._try_clean_future(parent)

    def _on_future_done(self, future: EventFuture) -> None:  # type: ignore[override]
        """Callback invoked when an enqueued future completes.

        If the future was cancelled externally, cancel the running task
        and all child futures.  If the task has not started yet,
        ``_process_queue`` will check the future and skip it when the
        entry is dequeued.

        Args:
            future: The EventFuture that completed.
        """
        if not future.cancelled():
            return
        # Cascade cancellation to all child futures.
        for child in future.children:
            child.cancel()
        task = self._tasks.get(future.txid)
        if task is not None:
            task.cancel()

    async def _execute_event(
        self, *, entry: EventQueueEntry, registered_handler: RegisteredEventHandler
    ) -> None:
        """Execute the handler for a single event queue entry.

        This method contains the actual event-processing logic.  The base
        implementation simply invokes the registered handler function with the
        event payload.  Subclasses (e.g. ``BaseStateEventProcessor``) override
        this method to add state management, delta emission, and middleware.

        ``_process_event_queue_entry`` is responsible for setting up the
        ``EventContext`` and ensuring sequential ordering *before* calling this
        method.

        Args:
            entry: The event queue entry to process.
            registered_handler: The registered handler for the event.
        """
        event = entry.event
        result = registered_handler.handler.fn(**event.payload)
        if inspect.isawaitable(result):
            await result

    async def _process_event_queue_entry(
        self, *, entry: EventQueueEntry, registered_handler: RegisteredEventHandler
    ) -> None:
        """Process a single event queue entry.

        This function runs in a new task for each event.  It sets up the
        ``EventContext``, enforces sequential ordering for non-background
        events, and then delegates to ``_execute_event`` for the actual
        handler invocation.

        Subclasses should override ``_execute_event`` rather than this method
        so that the shared context setup and sequential-ordering logic is
        always applied.

        Args:
            entry: The event queue entry to process.
            registered_handler: The registered handler for the event.
        """
        # Set up the event context for this task.
        EventContext.set(entry.ctx)
        await self._execute_event(entry=entry, registered_handler=registered_handler)

    def _create_event_task(
        self,
        *,
        entry: EventQueueEntry,
        registered_handler: RegisteredEventHandler,
    ) -> asyncio.Task:
        """Create and register an asyncio task for processing a single event.

        Args:
            entry: The event queue entry to process.
            registered_handler: The registered handler for the event.

        Returns:
            The created asyncio.Task.
        """
        task = asyncio.create_task(
            self._process_event_queue_entry(
                entry=entry, registered_handler=registered_handler
            ),
            name=f"reflex_event|{entry.event.name}|{entry.ctx.token}|{time.time()}",
        )
        if sys.version_info < (3, 12):
            task._event_ctx = entry.ctx  # pyright: ignore[reportAttributeAccessIssue]
        self._tasks[entry.ctx.txid] = task
        task.add_done_callback(self._finish_task)
        return task

    def _enqueue_for_token(
        self,
        *,
        entry: EventQueueEntry,
        registered_handler: RegisteredEventHandler,
    ) -> None:
        """Append an event to the per-token queue and dispatch if idle.

        If no queue exists for the token yet, one is created. If this is
        the first (and therefore only) entry, a task is dispatched
        immediately.

        Args:
            entry: The event queue entry to enqueue.
            registered_handler: The registered handler for the event.
        """
        token = entry.ctx.token
        token_queue = self._token_queues.get(token)
        if token_queue is None:
            token_queue = self._token_queues[token] = collections.deque()
        token_queue.append((entry, registered_handler))
        if len(token_queue) == 1:
            self._dispatch_next_for_token(token)

    def _dispatch_next_for_token(self, token: str) -> None:
        """Create a task for the front entry in the per-token queue.

        Args:
            token: The client token whose queue to dispatch from.
        """
        token_queue = self._token_queues.get(token)
        if not token_queue:
            return
        entry, registered_handler = token_queue[0]
        # Skip cancelled futures.
        future = self._futures.get(entry.ctx.txid)
        if future is not None and future.cancelled():
            self._try_clean_future(future)
            token_queue.popleft()
            if token_queue:
                self._dispatch_next_for_token(token)
            else:
                del self._token_queues[token]
            return
        self._create_event_task(entry=entry, registered_handler=registered_handler)

    async def _process_queue(self):
        """Process events from the queue in a task."""
        if (queue := self._queue) is None:
            msg = "Event processor is not running, call .start(...) first."
            raise RuntimeError(msg)
        with contextlib.suppress(QueueShutDown):
            while True:
                entry = await queue.get()
                if (
                    future := self._futures.get(entry.ctx.txid)
                ) is not None and future.cancelled():
                    self._try_clean_future(future)
                    queue.task_done()
                    continue
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
                    if registered_handler.handler.is_background:
                        # Background events run immediately, bypassing per-token ordering.
                        self._create_event_task(
                            entry=entry, registered_handler=registered_handler
                        )
                    else:
                        # Sequential events go through the per-token queue.
                        self._enqueue_for_token(
                            entry=entry, registered_handler=registered_handler
                        )
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

    async def _handle_backend_exception(
        self, ex: Exception, ev_ctx: EventContext | None = None
    ) -> None:
        """Handle an exception raised during event processing by calling the backend exception handler if it exists.

        Args:
            ex: The exception that was raised.
            ev_ctx: The event context for the exception, if available. This will be set in the context variable when calling the exception handler.
        """
        if self.backend_exception_handler is not None:
            if ev_ctx is not None:
                EventContext.set(ev_ctx)
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

        if sys.version_info < (3, 12):
            # py3.11 compat
            task_ctx = task._event_ctx  # type: ignore[attr-defined]
        else:
            task_ctx = task.get_context().run(EventContext.get)
        self._tasks.pop(task_ctx.txid, None)
        # Chain the next sequential event for this token if applicable.
        token_queue = self._token_queues.get(task_ctx.token)
        if token_queue and token_queue[0][0].ctx.txid == task_ctx.txid:
            token_queue.popleft()
            if token_queue:
                self._dispatch_next_for_token(task_ctx.token)
            else:
                del self._token_queues[task_ctx.token]
        future = self._futures.get(task_ctx.txid)
        if task.done():
            try:
                result = task.result()
            except asyncio.CancelledError:
                if future is not None and not future.done():
                    future.cancel()
            except Exception as ex:
                if future is not None and not future.done():
                    future.set_exception(ex)
                    with contextlib.suppress(BaseException):
                        # Trigger the future to avoid warnings if the caller didn't wait.
                        future.result()
                telemetry.send_error(ex, context="backend")
                if (
                    not task.get_name().startswith("reflex_backend_exception_handler|")
                    and self.backend_exception_handler is not None
                ):
                    # Create a new task in the same context to invoke the exception handler.
                    t = self._tasks[task_ctx.txid] = asyncio.create_task(
                        self._handle_backend_exception(ex, ev_ctx=task_ctx),
                        name=f"reflex_backend_exception_handler|task=[{task.get_name()}]|{time.time()}",
                    )
                    if sys.version_info < (3, 12):
                        t._event_ctx = task_ctx  # pyright: ignore[reportAttributeAccessIssue]
                    t.add_done_callback(self._finish_task)
                    return
                console.error(
                    rich.markup.escape(
                        f"Error in {task.get_name()} [txid={task_ctx.txid}]:\n{traceback.format_exc()}"
                    )
                )
            else:
                if future is not None and not future.done():
                    future.set_result(result)


__all__ = [
    "EventFuture",
    "EventProcessor",
    "EventQueueEntry",
]
