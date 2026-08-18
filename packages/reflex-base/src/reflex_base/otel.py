"""OpenTelemetry trace points and metrics for the Reflex runtime.

The framework calls into this module at a small number of fixed points (event
dispatch, event context forks, state acquisition, socket messages). Every entry
point checks the module-level ``enabled`` flag first, so with no
instrumentation installed the cost is one attribute read: no span is started
and nothing is recorded (only no-op API objects exist, created at import).

The ``reflex-otel`` package flips the flag via :func:`enable` once a tracer
provider is available.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterator, Mapping
from contextlib import contextmanager
from time import perf_counter
from typing import TYPE_CHECKING, Any

from opentelemetry import context as otel_context
from opentelemetry import metrics, propagate, trace
from opentelemetry.context import Context
from opentelemetry.trace import SpanKind

from reflex_base.constants.base import Reflex

if TYPE_CHECKING:
    from reflex_base.event import Event
    from reflex_base.event.context import EventContext
    from reflex_base.registry import RegisteredEventHandler

INSTRUMENTATION_NAME = "reflex"

# Attribute keys emitted on Reflex spans and metrics.
ATTR_EVENT_NAME = "reflex.event.name"
ATTR_EVENT_TXID = "reflex.event.txid"
ATTR_EVENT_PARENT_TXID = "reflex.event.parent_txid"
ATTR_EVENT_BACKGROUND = "reflex.event.background"
ATTR_SESSION_ID = "session.id"
ATTR_CODE_FUNCTION_NAME = "code.function.name"
ATTR_ERROR_TYPE = "error.type"
ATTR_NETWORK_IO_DIRECTION = "network.io.direction"

# Metric instrument names.
METRIC_EVENT_DURATION = "reflex.event.duration"
METRIC_STATE_ACQUIRE_DURATION = "reflex.state.acquire.duration"
METRIC_WEBSOCKET_MESSAGE_SIZE = "reflex.websocket.message.size"
METRIC_WEBSOCKET_CONNECTIONS = "reflex.websocket.connections"

# Key of the W3C trace context carried in an event payload sent by the frontend.
TRACEPARENT_FIELD = "traceparent"

# Histogram bucket advisories: seconds (semconv http.server.request.duration) and bytes.
_DURATION_BUCKETS = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.075,
    0.1,
    0.25,
    0.5,
    0.75,
    1,
    2.5,
    5,
    7.5,
    10,
)
_SIZE_BUCKETS = (128, 512, 1024, 4096, 16384, 65536, 262144, 1048576, 4194304)

# An ASGI callable: (scope, receive, send) -> awaitable.
ASGIApp = Callable[..., Awaitable[None]]

# Read at every trace point; True only after enable() ran.
enabled: bool = False
# Wraps the app's ASGI callable when set (installed by enable()).
asgi_middleware: Callable[[ASGIApp], ASGIApp] | None = None

_tracer: trace.Tracer = trace.NoOpTracer()
_noop_meter = metrics.NoOpMeter(INSTRUMENTATION_NAME)
_event_duration = _noop_meter.create_histogram(METRIC_EVENT_DURATION)
_state_acquire_duration = _noop_meter.create_histogram(METRIC_STATE_ACQUIRE_DURATION)
_message_size = _noop_meter.create_histogram(METRIC_WEBSOCKET_MESSAGE_SIZE)
_ws_connections = _noop_meter.create_up_down_counter(METRIC_WEBSOCKET_CONNECTIONS)


def _create_instruments(meter: metrics.Meter) -> None:
    """Create the metric instruments on the given meter.

    Args:
        meter: The meter to create the instruments on.
    """
    global _event_duration, _state_acquire_duration, _message_size, _ws_connections
    _event_duration = meter.create_histogram(
        METRIC_EVENT_DURATION,
        unit="s",
        description="Duration of event handler executions.",
        explicit_bucket_boundaries_advisory=_DURATION_BUCKETS,
    )
    _state_acquire_duration = meter.create_histogram(
        METRIC_STATE_ACQUIRE_DURATION,
        unit="s",
        description="Time an event waited to acquire and load its session state.",
        explicit_bucket_boundaries_advisory=_DURATION_BUCKETS,
    )
    _message_size = meter.create_histogram(
        METRIC_WEBSOCKET_MESSAGE_SIZE,
        unit="By",
        description="Serialized size of socket messages exchanged with the client.",
        explicit_bucket_boundaries_advisory=_SIZE_BUCKETS,
    )
    _ws_connections = meter.create_up_down_counter(
        METRIC_WEBSOCKET_CONNECTIONS,
        unit="{connection}",
        description="Number of open client socket connections.",
    )


def enable(
    tracer_provider: trace.TracerProvider | None = None,
    meter_provider: metrics.MeterProvider | None = None,
    asgi_middleware_factory: Callable[[ASGIApp], ASGIApp] | None = None,
) -> None:
    """Turn the trace points and metrics on.

    Args:
        tracer_provider: The provider to obtain the tracer from. Defaults to
            the global provider, which may be configured later; the returned
            proxy tracer picks it up automatically.
        meter_provider: The provider to obtain the meter from. Defaults to the
            global provider.
        asgi_middleware_factory: Callable that wraps the app's ASGI callable,
            e.g. the OpenTelemetry ASGI middleware. Applied by the app when it
            builds its ASGI app.
    """
    global _tracer, enabled, asgi_middleware
    _tracer = trace.get_tracer(
        INSTRUMENTATION_NAME, Reflex.VERSION, tracer_provider=tracer_provider
    )
    _create_instruments(
        metrics.get_meter(
            INSTRUMENTATION_NAME, Reflex.VERSION, meter_provider=meter_provider
        )
    )
    asgi_middleware = asgi_middleware_factory
    enabled = True


def disable() -> None:
    """Turn the trace points off and drop the tracer and instruments."""
    global _tracer, enabled, asgi_middleware
    enabled = False
    asgi_middleware = None
    _tracer = trace.NoOpTracer()
    _create_instruments(_noop_meter)


def capture_context() -> Context | None:
    """Snapshot the current OpenTelemetry context for a forked event context.

    Returns:
        The current context when tracing is enabled, otherwise None.
    """
    return otel_context.get_current() if enabled else None


def attach_context(context: Context | None) -> None:
    """Make a captured context current for the rest of the running task.

    Args:
        context: The context to attach; None is ignored.
    """
    if context is not None:
        otel_context.attach(context)


class _AttachedContext:
    """Attach a context on enter and detach it on exit."""

    __slots__ = ("_context", "_token")

    def __init__(self, context: Context):
        """Store the context to attach.

        Args:
            context: The context to make current.
        """
        self._context = context

    def __enter__(self) -> None:
        """Attach the context."""
        self._token = otel_context.attach(self._context)

    def __exit__(self, *exc_info: object) -> None:
        """Detach the context.

        Args:
            *exc_info: Ignored exception details.
        """
        otel_context.detach(self._token)


def remote_context(carrier: Mapping[str, Any]) -> _AttachedContext:
    """Make the trace context carried by a frontend event the current context.

    Only call when ``enabled``. Events that carry no ``traceparent`` start a
    new trace: the websocket connection span (if any) is deliberately not
    used as their parent.

    Args:
        carrier: The raw event fields received from the frontend.

    Returns:
        A context manager to run the enqueue under.
    """
    return _AttachedContext(propagate.extract(carrier, context=Context()))


@contextmanager
def event_span(
    event: Event, ctx: EventContext, registered_handler: RegisteredEventHandler
) -> Iterator[trace.Span]:
    """Open the span for one event handler execution and record its duration.

    Chained events are INTERNAL children of the span that enqueued them;
    events that arrive from the frontend are SERVER spans (a new trace, or a
    child of the browser's remote span).

    Args:
        event: The event being processed.
        ctx: The event context for this execution.
        registered_handler: The handler resolved for the event.

    Yields:
        The active span.
    """
    handler = registered_handler.handler
    metric_attributes = {
        ATTR_EVENT_NAME: event.name,
        ATTR_EVENT_BACKGROUND: handler.is_background,
    }
    attributes: dict[str, Any] = {
        **metric_attributes,
        ATTR_EVENT_TXID: ctx.txid,
        ATTR_SESSION_ID: ctx.token,
        ATTR_CODE_FUNCTION_NAME: getattr(handler.fn, "__qualname__", event.name),
    }
    if ctx.parent_txid:
        attributes[ATTR_EVENT_PARENT_TXID] = ctx.parent_txid
    # An event whose parent span is local (a chained event) is an internal
    # step of that request; anything else is a new inbound request.
    parent = trace.get_current_span(ctx.otel_context).get_span_context()
    kind = (
        SpanKind.INTERNAL
        if parent.is_valid and not parent.is_remote
        else SpanKind.SERVER
    )
    with _tracer.start_as_current_span(
        event.name, context=ctx.otel_context, kind=kind, attributes=attributes
    ) as span:
        # Record while the span is still current: exporter latency stays out
        # of the sample and exemplars keep the trace/span IDs.
        start = perf_counter()
        try:
            yield span
        except Exception as ex:
            metric_attributes[ATTR_ERROR_TYPE] = type(ex).__qualname__
            raise
        finally:
            _event_duration.record(perf_counter() - start, metric_attributes)


def record_state_acquired(start: float, event: Event) -> None:
    """Record how long an event waited for its session state.

    Args:
        start: ``perf_counter()`` value taken before the state was requested.
        event: The event that acquired the state.
    """
    _state_acquire_duration.record(
        perf_counter() - start, {ATTR_EVENT_NAME: event.name}
    )


def record_message_size(size: int, direction: str) -> None:
    """Record the serialized size of one socket message.

    Args:
        size: The message size in bytes.
        direction: ``"transmit"`` for server-to-client, ``"receive"`` otherwise.
    """
    _message_size.record(size, {ATTR_NETWORK_IO_DIRECTION: direction})


def record_connection(delta: int) -> None:
    """Adjust the open socket connection count.

    Args:
        delta: ``1`` on connect, ``-1`` on disconnect.
    """
    _ws_connections.add(delta)
