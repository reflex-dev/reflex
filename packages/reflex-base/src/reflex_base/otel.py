"""OpenTelemetry trace points and metrics for the Reflex runtime.

The framework calls into this module at a small number of fixed points (event
dispatch, event context forks, state acquisition, socket messages). Every entry
point checks the module-level ``enabled`` flag first, so with no
instrumentation installed the cost is one attribute read and no
``opentelemetry`` object is ever created.

The ``reflex-otel`` package flips the flag via :func:`enable` once a tracer
provider is available.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager, nullcontext
from time import perf_counter
from typing import TYPE_CHECKING, Any

from opentelemetry import context as otel_context
from opentelemetry import metrics, propagate, trace
from opentelemetry.context import Context
from opentelemetry.trace import SpanKind

from reflex_base.constants.base import Reflex

if TYPE_CHECKING:
    from contextlib import AbstractContextManager

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

# Read at every trace point; True only after enable() ran.
enabled: bool = False
# Wraps the app's ASGI callable when set (installed by enable()).
asgi_middleware: Callable[[Any], Any] | None = None

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
    )
    _state_acquire_duration = meter.create_histogram(
        METRIC_STATE_ACQUIRE_DURATION,
        unit="s",
        description="Time an event waited to acquire and load its session state.",
    )
    _message_size = meter.create_histogram(
        METRIC_WEBSOCKET_MESSAGE_SIZE,
        unit="By",
        description="Serialized size of socket messages exchanged with the client.",
    )
    _ws_connections = meter.create_up_down_counter(
        METRIC_WEBSOCKET_CONNECTIONS,
        unit="{connection}",
        description="Number of open client socket connections.",
    )


def enable(
    tracer_provider: trace.TracerProvider | None = None,
    meter_provider: metrics.MeterProvider | None = None,
    asgi_middleware_factory: Callable[[Any], Any] | None = None,
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


def remote_context(carrier: Mapping[str, Any]) -> AbstractContextManager[None]:
    """Make the trace context carried by a frontend event the current context.

    Events that carry no ``traceparent`` start a new trace: the websocket
    connection span (if any) is deliberately not used as their parent.

    Args:
        carrier: The raw event fields received from the frontend.

    Returns:
        A context manager to run the enqueue under; a no-op when tracing is off.
    """
    if not enabled:
        return nullcontext()
    return _AttachedContext(propagate.extract(carrier, context=Context()))


@contextmanager
def event_span(
    event: Event, ctx: EventContext, registered_handler: RegisteredEventHandler
) -> Iterator[trace.Span]:
    """Open the span for one event handler execution and record its duration.

    Chained events are parented under the span that enqueued them; events
    that arrive from the frontend start a new trace.

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
    start = perf_counter()
    try:
        with _tracer.start_as_current_span(
            event.name,
            context=ctx.otel_context,
            kind=SpanKind.SERVER,
            attributes=metric_attributes
            | {
                ATTR_EVENT_TXID: ctx.txid,
                ATTR_SESSION_ID: ctx.token,
                ATTR_CODE_FUNCTION_NAME: getattr(
                    handler.fn, "__qualname__", event.name
                ),
            }
            | ({ATTR_EVENT_PARENT_TXID: ctx.parent_txid} if ctx.parent_txid else {}),
        ) as span:
            yield span
    except BaseException as ex:
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
