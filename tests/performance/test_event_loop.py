"""Wall-time event-loop, queueing, ordering, and blocking benchmarks."""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import time
from collections import defaultdict
from collections.abc import AsyncIterator, Mapping
from pathlib import Path
from typing import Any

import pytest
from reflex_base.event.context import EventContext
from reflex_base.event.processor import BaseStateEventProcessor
from reflex_base.event.processor.event_processor import EventProcessor, EventQueueEntry
from reflex_base.registry import RegisteredEventHandler, RegistrationContext
from typing_extensions import Unpack, override

import reflex as rx
from reflex.event import Event, EventHandler
from reflex.istate.manager import StateModificationContext
from reflex.istate.manager.memory import StateManagerMemory
from reflex.istate.manager.token import TOKEN_TYPE, StateToken
from reflex.state import BaseState
from tests.benchmarks.support import (
    BenchmarkResult,
    EventLoopProbe,
    PerformanceReport,
    PipelineTrace,
    capture_async_diagnostics,
)
from tests.benchmarks.support.pipeline_trace import StageEvent
from tests.benchmarks.support.report import (
    current_process_metrics,
    percentile,
    runtime_metadata,
)

_ORDER_LOG: dict[str, list[int]] = defaultdict(list)
_ACTIVE_STATE_TRACE: PipelineTrace | None = None

# Deliberate synchronous block injected by the blocking scenario. Detection is
# asserted at >=2ms of measured loop lag, so 10ms leaves a 5x margin even on a
# loaded CI runner.
_BLOCKING_SLEEP_SECONDS = 0.01

# Generous stall guard for event-future waits: a stuck future is the exact
# regression class this suite exists to catch and must fail fast, not hang CI.
_EVENT_WAIT_BASE_TIMEOUT_SECONDS = 60.0
_EVENT_WAIT_PER_EVENT_SECONDS = 0.1


async def _wait_events_bounded(awaitable: Any, *, events: int, scenario: str) -> None:
    """Await event-future completion with a stall-detecting timeout.

    Args:
        awaitable: The future wait (or gather of waits) to bound.
        events: Number of in-flight events, scaling the allowance.
        scenario: Scenario name for the failure message.
    """
    timeout = _EVENT_WAIT_BASE_TIMEOUT_SECONDS + events * _EVENT_WAIT_PER_EVENT_SECONDS
    try:
        await asyncio.wait_for(awaitable, timeout=timeout)
    except asyncio.TimeoutError:
        pytest.fail(
            f"{scenario}: {events} event future(s) still pending after "
            f"{timeout:.0f}s; the event pipeline is stuck"
        )


def _record_state_stage(stage: str) -> None:
    """Record a stage for the active state event.

    Args:
        stage: Pipeline stage name.
    """
    trace = _ACTIVE_STATE_TRACE
    assert trace is not None
    trace.record(EventContext.get().txid, stage)


class AttributionState(rx.State):
    """State whose handler exposes precise benchmark-only boundaries."""

    value: rx.Field[int] = rx.field(0)

    @rx.event
    def increment(self):
        """Record handler and pre-delta boundaries around a mutation."""
        _record_state_stage("handler_started")
        self.value += 1
        _record_state_stage("handler_finished")
        _record_state_stage("delta_started")

    @rx.event
    def cpu_heavy(self):
        """Perform synchronous CPU work on the event loop."""
        _record_state_stage("handler_started")
        self.value += sum(range(100_000))
        _record_state_stage("handler_finished")
        _record_state_stage("delta_started")

    @rx.event
    def blocking(self):
        """Perform a deliberately blocking synchronous wait."""
        _record_state_stage("handler_started")
        time.sleep(0.005)
        self.value += 1
        _record_state_stage("handler_finished")
        _record_state_stage("delta_started")

    @rx.event
    async def thread_offload(self):
        """Move CPU work off the event-loop thread."""
        _record_state_stage("handler_started")
        self.value += await asyncio.to_thread(sum, range(100_000))
        _record_state_stage("handler_finished")
        _record_state_stage("delta_started")

    @rx.event
    def sync_generator(self):
        """Yield three synchronous intermediate state updates."""
        _record_state_stage("handler_started")
        for _ in range(3):
            self.value += 1
            _record_state_stage("delta_started")
            yield
        _record_state_stage("handler_finished")

    @rx.event
    async def async_generator(self):
        """Yield three cooperative asynchronous state updates."""
        _record_state_stage("handler_started")
        for _ in range(3):
            await asyncio.sleep(0)
            self.value += 1
            _record_state_stage("delta_started")
            yield
        _record_state_stage("handler_finished")

    @rx.event
    def failure(self):
        """Raise an exception after recording handler entry."""
        _record_state_stage("handler_started")
        msg = "intentional performance scenario failure"
        raise RuntimeError(msg)


class TracingStateManagerMemory(StateManagerMemory):
    """Memory manager recording lock and state-flush boundaries."""

    def __init__(self, trace: PipelineTrace):
        """Initialize the manager.

        Args:
            trace: Pipeline trace receiving observations.
        """
        super().__init__()
        self.trace = trace

    @override
    @contextlib.asynccontextmanager
    async def modify_state(
        self,
        token: StateToken[TOKEN_TYPE],
        **context: Unpack[StateModificationContext],
    ) -> AsyncIterator[TOKEN_TYPE]:
        """Record lock wait, hold, and flush stages.

        Args:
            token: Managed state token.
            context: State modification context.

        Yields:
            Managed state.
        """
        transaction = EventContext.get().txid
        self.trace.record(transaction, "lock_wait_started")
        async with super().modify_state(token, **context) as state:
            self.trace.record(transaction, "lock_acquired")
            try:
                yield state
            finally:
                self.trace.record(transaction, "state_flush_started")
        self.trace.record(transaction, "state_flush_finished")
        self.trace.record(transaction, "lock_released")


class AttributionEventProcessor(BaseStateEventProcessor):
    """State processor that omits first-connect hydration from attribution."""

    @override
    async def _rehydrate(self, root_state: BaseState) -> None:
        """Skip hydration so the scenario isolates one application event.

        Args:
            root_state: Root state, intentionally unused.
        """


async def _cooperative_handler(sequence: int) -> None:
    """Yield to the loop before recording event completion.

    Args:
        sequence: Per-token event sequence.
    """
    await asyncio.sleep(0.001)
    _ORDER_LOG[EventContext.get().token].append(sequence)


async def _blocking_handler(sequence: int) -> None:  # noqa: RUF029
    """Deliberately block the loop before recording completion.

    Args:
        sequence: Per-token event sequence.
    """
    time.sleep(_BLOCKING_SLEEP_SECONDS)  # noqa: ASYNC251 - intentional benchmark scenario
    _ORDER_LOG[EventContext.get().token].append(sequence)


COOPERATIVE_EVENT = EventHandler(fn=_cooperative_handler)
BLOCKING_EVENT = EventHandler(fn=_blocking_handler)


class TracingEventProcessor(EventProcessor):
    """Event processor that records benchmark-only task pipeline stages."""

    def __init__(self, graceful_shutdown_timeout: float | None = None):
        """Initialize the processor and its isolated trace.

        Args:
            graceful_shutdown_timeout: Maximum graceful drain time.
        """
        super().__init__(graceful_shutdown_timeout=graceful_shutdown_timeout)
        self.trace = PipelineTrace()

    async def enqueue(self, token: str, event: Event, ev_ctx=None):
        """Record ingress and queue completion around normal enqueue.

        Args:
            token: Client token.
            event: Event to enqueue.
            ev_ctx: Optional existing event context.

        Returns:
            Tracked event future.
        """
        started = time.perf_counter_ns()
        future = await super().enqueue(token, event, ev_ctx)
        self.trace.extend([
            _stage(future.txid, "received", started),
            _stage(future.txid, "enqueued", time.perf_counter_ns()),
        ])
        return future

    def _enqueue_for_token(
        self,
        *,
        entry: EventQueueEntry,
        registered_handler: RegisteredEventHandler,
    ) -> None:
        """Record shared-queue dequeue and per-token queue entry."""
        self.trace.record(entry.ctx.txid, "dequeued")
        self.trace.record(entry.ctx.txid, "token_queued")
        super()._enqueue_for_token(
            entry=entry,
            registered_handler=registered_handler,
        )

    def _create_event_task(
        self,
        *,
        entry: EventQueueEntry,
        registered_handler: RegisteredEventHandler,
    ) -> asyncio.Task:
        """Record when per-token ordering permits task creation.

        Returns:
            Created event task.
        """
        self.trace.record(entry.ctx.txid, "token_ready")
        self.trace.record(entry.ctx.txid, "task_created")
        return super()._create_event_task(
            entry=entry,
            registered_handler=registered_handler,
        )

    async def _process_event_queue_entry(
        self,
        *,
        entry: EventQueueEntry,
        registered_handler: RegisteredEventHandler,
    ) -> None:
        """Record scheduling, handler, and completion boundaries."""
        self.trace.record(entry.ctx.txid, "task_started")
        self.trace.record(entry.ctx.txid, "handler_started")
        try:
            await super()._process_event_queue_entry(
                entry=entry,
                registered_handler=registered_handler,
            )
        finally:
            self.trace.record(entry.ctx.txid, "handler_finished")
            self.trace.record(entry.ctx.txid, "completed")


def _stage(token: str, stage: str, timestamp_ns: int) -> StageEvent:
    """Create a pipeline stage without another clock read.

    Args:
        token: Transaction identifier.
        stage: Stage name.
        timestamp_ns: Existing monotonic timestamp.

    Returns:
        Stage event.
    """
    return StageEvent(token, stage, timestamp_ns)


async def _run_scenario(
    handler: EventHandler,
    *,
    tokens: int,
    events_per_token: int,
    probe_interval: float,
    hot_token_fraction: float = 0,
) -> tuple[list[float], dict[str, float | int], PipelineTrace]:
    """Run one event-loop scenario and collect latency and resource metrics.

    Args:
        handler: Registered workload handler.
        tokens: Number of independent client tokens.
        events_per_token: Sequential events per token.
        probe_interval: Loop-lag sample interval.
        hot_token_fraction: Fraction of all work assigned to token zero.

    Returns:
        Latencies, probe/resource metrics, and pipeline trace.
    """
    _ORDER_LOG.clear()
    processor = TracingEventProcessor(graceful_shutdown_timeout=2)
    processor.configure()

    def queue_depth() -> int:
        """Return shared queue depth."""
        return processor._queue.qsize() if processor._queue is not None else 0

    def token_queue_depth() -> int:
        """Return total queued per-token work."""
        return sum(len(queue) for queue in processor._token_queues.values())

    probe = EventLoopProbe(
        interval=probe_interval,
        gauges={
            "queue_depth": queue_depth,
            "token_queue_depth": token_queue_depth,
            "processor_tasks": lambda: len(processor._tasks),
        },
    )
    latencies: list[float] = []
    started: dict[str, int] = {}
    expected_order: dict[str, list[int]] = defaultdict(list)
    if hot_token_fraction:
        total_events = tokens * events_per_token
        hot_events = int(total_events * hot_token_fraction)
        token_events = [("token-0", sequence) for sequence in range(hot_events)]
        for offset in range(total_events - hot_events):
            token_index = 1 + offset % max(1, tokens - 1)
            token = f"token-{token_index}"
            token_events.append((token, len(expected_order[token])))
            expected_order[token].append(len(expected_order[token]))
        expected_order["token-0"] = list(range(hot_events))
    else:
        token_events = [
            (f"token-{token_index}", sequence)
            for token_index in range(tokens)
            for sequence in range(events_per_token)
        ]
        for token_index in range(tokens):
            expected_order[f"token-{token_index}"] = list(range(events_per_token))

    async with probe, processor:
        futures = []
        for token, sequence in token_events:
            future = await processor.enqueue(
                token,
                Event.from_event_type(handler(sequence))[0],
            )
            started[future.txid] = time.perf_counter_ns()
            future.add_done_callback(
                lambda completed, txid=future.txid: latencies.append(
                    (time.perf_counter_ns() - started[txid]) / 1_000_000
                )
            )
            futures.append(future)
        await _wait_events_bounded(
            asyncio.gather(*(future.wait_all() for future in futures)),
            events=len(futures),
            scenario=handler.fn.__name__,
        )
        await asyncio.sleep(probe_interval * 2)

    for token, expected in expected_order.items():
        assert _ORDER_LOG[token] == expected
    assert not processor._tasks
    assert not processor._futures
    durations = processor.trace.durations_ms([
        ("received", "enqueued"),
        ("enqueued", "dequeued"),
        ("dequeued", "task_started"),
        ("token_queued", "token_ready"),
        ("task_created", "task_started"),
        ("handler_started", "handler_finished"),
    ])
    stage_metrics = {
        f"{name}_p95_ms": percentile(observations, 95)
        for name, observations in durations.items()
    }
    metrics = (
        probe.summary()
        | current_process_metrics()
        | stage_metrics
        | {
            "tasks_created": sum(
                event.stage == "task_created" for event in processor.trace.events
            ),
            "orphan_tasks": len(processor._tasks),
            "orphan_futures": len(processor._futures),
        }
    )
    return latencies, metrics, processor.trace


async def _run_state_pipeline(
    handler: Any,
) -> tuple[float, dict[str, float | int], PipelineTrace]:
    """Run a full state mutation, delta, flush, and emit pipeline.

    Returns:
        End-to-end latency, stage metrics, and trace.
    """
    global _ACTIVE_STATE_TRACE
    trace = PipelineTrace()
    _ACTIVE_STATE_TRACE = trace
    manager = TracingStateManagerMemory(trace)
    processor = AttributionEventProcessor(graceful_shutdown_timeout=2)
    processor.configure(state_manager=manager)
    assert processor._root_context is not None  # pyright: ignore [reportPrivateUsage]

    async def emit_delta(
        _token: str,
        _delta: Mapping[str, Mapping[str, Any]],
    ) -> None:
        """Record delta completion and simulated socket flush boundaries."""
        transaction = EventContext.get().txid
        trace.record(transaction, "delta_finished")
        trace.record(transaction, "emit_started")
        await asyncio.sleep(0)
        trace.record(transaction, "emit_finished")

    processor._root_context = dataclasses.replace(  # pyright: ignore [reportPrivateUsage]
        processor._root_context,  # pyright: ignore [reportPrivateUsage]
        emit_delta_impl=emit_delta,
    )
    event = Event.from_event_type(handler())[0]
    event = dataclasses.replace(event, router_data={"path": "/", "query": {}})
    started = time.perf_counter_ns()
    try:
        async with processor:
            received = time.perf_counter_ns()
            future = await processor.enqueue("attribution-token", event)
            trace.extend([
                StageEvent(future.txid, "received", received),
                StageEvent(future.txid, "enqueued", time.perf_counter_ns()),
            ])
            await _wait_events_bounded(
                future.wait_all(), events=1, scenario="state_pipeline"
            )
    finally:
        await manager.close()
        _ACTIVE_STATE_TRACE = None
    elapsed = (time.perf_counter_ns() - started) / 1_000_000
    durations = trace.durations_ms([
        ("received", "enqueued"),
        ("lock_wait_started", "lock_acquired"),
        ("handler_started", "handler_finished"),
        ("delta_started", "delta_finished"),
        ("state_flush_started", "state_flush_finished"),
        ("emit_started", "emit_finished"),
        ("lock_acquired", "lock_released"),
    ])
    metrics: dict[str, float | int] = {}
    for name, observations in durations.items():
        metrics[f"{name}_p95_ms"] = percentile(observations, 95)
    return elapsed, metrics, trace


async def _run_failed_state_pipeline() -> None:
    """Verify exception cleanup leaves no processor tasks or futures."""
    global _ACTIVE_STATE_TRACE
    trace = PipelineTrace()
    _ACTIVE_STATE_TRACE = trace
    manager = TracingStateManagerMemory(trace)
    exceptions: list[Exception] = []
    processor = AttributionEventProcessor(
        graceful_shutdown_timeout=2,
        backend_exception_handler=exceptions.append,
    )
    processor.configure(state_manager=manager)
    event = Event.from_event_type(AttributionState.failure())[0]
    event = dataclasses.replace(event, router_data={"path": "/", "query": {}})
    try:
        async with processor:
            future = await processor.enqueue("failure-token", event)
            with contextlib.suppress(RuntimeError):
                await _wait_events_bounded(
                    future.wait_all(), events=1, scenario="failed_state_pipeline"
                )
    finally:
        await manager.close()
        _ACTIVE_STATE_TRACE = None
    assert exceptions
    assert not processor._tasks
    assert not processor._futures


@pytest.mark.performance
async def test_event_loop_component_report(
    performance_output: Path,
    performance_scale: str,
):
    """Measure cooperative, contended, concurrent, and blocking event workloads.

    Args:
        performance_output: Artifact directory.
        performance_scale: Selected scenario scale.
    """
    scales = {
        "smoke": (5, 4, 10),
        "release": (200, 50, 1000),
    }
    independent_tokens, independent_events, same_token_events = scales[
        performance_scale
    ]
    scenarios = [
        ("same_token", COOPERATIVE_EVENT, 1, same_token_events, 0),
        (
            "independent_tokens",
            COOPERATIVE_EVENT,
            independent_tokens,
            independent_events,
            0,
        ),
        (
            "hot_token_80_20",
            COOPERATIVE_EVENT,
            max(5, independent_tokens),
            independent_events,
            0.8,
        ),
        ("blocking_handler", BLOCKING_EVENT, 2, 5, 0),
    ]
    registry = RegistrationContext()
    with registry:
        for handler in (COOPERATIVE_EVENT, BLOCKING_EVENT):
            RegistrationContext.register_event_handler(handler)
        RegistrationContext.register_base_state(AttributionState)

        report = PerformanceReport(
            "event-loop",
            metadata=runtime_metadata() | {"scale": performance_scale},
        )
        traces: list[PipelineTrace] = []
        for name, handler, tokens, events_per_token, hot_fraction in scenarios:
            latencies, metrics, trace = await _run_scenario(
                handler,
                tokens=tokens,
                events_per_token=events_per_token,
                probe_interval=0.001,
                hot_token_fraction=hot_fraction,
            )
            report.add(
                BenchmarkResult(
                    name=name,
                    parameters={
                        "tokens": tokens,
                        "events_per_token": events_per_token,
                        "hot_token_fraction": hot_fraction,
                    },
                    observations_ms=latencies,
                    metrics=metrics,
                    measurement_iterations=len(latencies),
                )
            )
            traces.append(trace)

        for state_name, state_handler in [
            ("state_pipeline_attribution", AttributionState.increment),
            ("cpu_heavy_handler", AttributionState.cpu_heavy),
            ("blocking_state_handler", AttributionState.blocking),
            ("thread_offload_handler", AttributionState.thread_offload),
            ("sync_generator_handler", AttributionState.sync_generator),
            ("async_generator_handler", AttributionState.async_generator),
        ]:
            state_latency, state_metrics, state_trace = await _run_state_pipeline(
                state_handler
            )
            report.add(
                BenchmarkResult(
                    name=state_name,
                    parameters={"state_manager": "memory"},
                    observations_ms=[state_latency],
                    metrics=state_metrics,
                    measurement_iterations=1,
                )
            )
            traces.append(state_trace)
        await _run_failed_state_pipeline()

    report.write(performance_output / "event-loop.json")
    combined_trace = PipelineTrace()
    for trace in traces:
        combined_trace.extend(trace.events)
    combined_trace.write_chrome_trace(performance_output / "event-loop.trace.json")

    assert report.results
    blocking = next(
        result for result in report.results if result.name == "blocking_handler"
    )
    # The probe must detect the deliberately induced block: each blocking event
    # stalls the loop for _BLOCKING_SLEEP_SECONDS (10ms), so 2ms of measured
    # lag is a 5x-margin detection bound, not a performance threshold.
    assert blocking.metrics["lag_max_ms"] >= 2
    capture_async_diagnostics(
        performance_output / "event-loop-blocking-diagnostics.json",
        metadata={
            "scenario": blocking.name,
            "metrics": dict(blocking.metrics),
            "last_stages": {
                event.token: event.stage for event in combined_trace.events
            },
        },
    )
