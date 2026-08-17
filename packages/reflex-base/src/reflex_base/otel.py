"""OpenTelemetry trace points for the Reflex runtime.

The framework calls into this module at a small number of fixed points (event
dispatch, event context forks). Every entry point checks the module-level
``enabled`` flag first, so with no instrumentation installed the cost is one
attribute read and no ``opentelemetry`` object is ever created.

The ``reflex-otel`` package flips the flag via :func:`enable` once a tracer
provider is available.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.trace import SpanKind

from reflex_base.constants.base import Reflex

if TYPE_CHECKING:
    from opentelemetry.context import Context

    from reflex_base.event import Event
    from reflex_base.event.context import EventContext
    from reflex_base.registry import RegisteredEventHandler

INSTRUMENTATION_NAME = "reflex"

# Attribute keys emitted on Reflex spans.
ATTR_EVENT_NAME = "reflex.event.name"
ATTR_EVENT_TXID = "reflex.event.txid"
ATTR_EVENT_PARENT_TXID = "reflex.event.parent_txid"
ATTR_EVENT_BACKGROUND = "reflex.event.background"
ATTR_SESSION_ID = "session.id"
ATTR_CODE_FUNCTION_NAME = "code.function.name"

# Read at every trace point; True only after enable() ran.
enabled: bool = False
_tracer: trace.Tracer = trace.NoOpTracer()


def enable(tracer_provider: trace.TracerProvider | None = None) -> None:
    """Turn the trace points on.

    Args:
        tracer_provider: The provider to obtain the tracer from. Defaults to
            the global provider, which may be configured later; the returned
            proxy tracer picks it up automatically.
    """
    global _tracer, enabled
    _tracer = trace.get_tracer(
        INSTRUMENTATION_NAME, Reflex.VERSION, tracer_provider=tracer_provider
    )
    enabled = True


def disable() -> None:
    """Turn the trace points off and drop the tracer."""
    global _tracer, enabled
    enabled = False
    _tracer = trace.NoOpTracer()


def capture_context() -> Context | None:
    """Snapshot the current OpenTelemetry context for a forked event context.

    Returns:
        The current context when tracing is enabled, otherwise None.
    """
    return otel_context.get_current() if enabled else None


@contextmanager
def event_span(
    event: Event, ctx: EventContext, registered_handler: RegisteredEventHandler
) -> Iterator[trace.Span]:
    """Open the span for one event handler execution.

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
    with _tracer.start_as_current_span(
        event.name,
        context=ctx.otel_context,
        kind=SpanKind.SERVER,
        attributes={
            ATTR_EVENT_NAME: event.name,
            ATTR_EVENT_TXID: ctx.txid,
            ATTR_EVENT_BACKGROUND: handler.is_background,
            ATTR_SESSION_ID: ctx.token,
            ATTR_CODE_FUNCTION_NAME: getattr(handler.fn, "__qualname__", event.name),
        }
        | ({ATTR_EVENT_PARENT_TXID: ctx.parent_txid} if ctx.parent_txid else {}),
    ) as span:
        yield span
