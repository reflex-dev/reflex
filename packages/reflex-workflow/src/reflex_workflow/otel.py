"""OpenTelemetry trace points for the workflow engine.

The engine calls into this module where a step is scheduled and where one runs.
Every entry point checks the module-level ``enabled`` flag first, so with no
instrumentation installed the cost is one attribute read and nothing from
``opentelemetry`` is imported. ``reflex-otel`` flips the flag through
:func:`enable`, which also binds the API modules the trace points use.
"""

from __future__ import annotations

from contextlib import nullcontext
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import MutableMapping
    from contextlib import AbstractContextManager

    from opentelemetry import context as context_api
    from opentelemetry import trace
    from opentelemetry.propagators.textmap import TextMapPropagator

INSTRUMENTATION_NAME = "reflex_workflow"

ATTR_TABLE = "reflex.workflow.table"
ATTR_STEP = "reflex.workflow.step"
ATTR_ATTEMPT = "reflex.workflow.attempt"
ATTR_LANE = "reflex.workflow.lane"
ATTR_OUTCOME = "reflex.workflow.outcome"
ATTR_ERROR_TYPE = "error.type"

# Where a scheduled step's producer context is kept, among the arguments stored
# in ``next_args``. Written only while enabled; stripped before the step runs.
TRACE_KEY = "traceparent"

# Outcomes that mark the attempt's span as failed.
_ERROR_OUTCOMES = frozenset({"retry", "failed"})

# Read at every trace point; True only after enable() ran.
enabled: bool = False

# Bound by enable().
_tracer: trace.Tracer
_propagator: TextMapPropagator


def enable(tracer_provider: trace.TracerProvider | None = None) -> None:
    """Turn the trace points on.

    Args:
        tracer_provider: The provider to obtain the tracer from. Defaults to
            the global provider.
    """
    global _tracer, _propagator, enabled, context_api, trace
    if enabled:
        return
    from importlib.metadata import PackageNotFoundError, version

    from opentelemetry import context as context_api
    from opentelemetry import trace
    from opentelemetry.trace.propagation.tracecontext import (
        TraceContextTextMapPropagator,
    )

    try:
        package_version = version("reflex-workflow")
    except PackageNotFoundError:
        package_version = None
    _propagator = TraceContextTextMapPropagator()
    _tracer = trace.get_tracer(
        INSTRUMENTATION_NAME, package_version, tracer_provider=tracer_provider
    )
    enabled = True


def disable() -> None:
    """Turn the trace points off."""
    global enabled
    enabled = False


def stamp(payload: dict[str, Any]) -> dict[str, Any]:
    """Add the current trace context to a step's stored arguments.

    Args:
        payload: The arguments about to be written to ``next_args``.

    Returns:
        The payload, carrying a ``traceparent`` when a span is current.
    """
    if not enabled:
        return payload
    # Typed as the propagator's default setter wants it.
    carrier: MutableMapping[str, list[str] | str] = {}
    _propagator.inject(carrier)
    if isinstance(traceparent := carrier.get(TRACE_KEY), str):
        payload[TRACE_KEY] = traceparent
    return payload


def step_span(
    table: str,
    step: str,
    attempt: int,
    lane: str | None,
    traceparent: object,
) -> AbstractContextManager[trace.Span | None]:
    """Open the span for one attempt of a step.

    The span is a trace root: a step runs on whichever worker claims it,
    possibly long after it was scheduled, so it links to the span that scheduled
    it instead of nesting under it, and never under whatever context the worker
    happened to inherit.

    Args:
        table: The workflow's table name.
        step: The step's name.
        attempt: Which attempt this is, counting from 1.
        lane: The lane the step runs in, when its class still declares it.
        traceparent: The ``traceparent`` stored with the step, if any.

    Returns:
        A context manager yielding the span (or None when tracing is off).
    """
    if not enabled:
        return nullcontext()
    attributes: dict[str, Any] = {
        ATTR_TABLE: table,
        ATTR_STEP: step,
        ATTR_ATTEMPT: attempt,
    }
    if lane is not None:
        attributes[ATTR_LANE] = lane
    links = []
    if isinstance(traceparent, str):
        producer = trace.get_current_span(
            _propagator.extract({TRACE_KEY: traceparent}, context=context_api.Context())
        ).get_span_context()
        if producer.is_valid:
            links.append(trace.Link(producer))
    return _tracer.start_as_current_span(
        f"{table}.{step}",
        context=context_api.Context(),
        kind=trace.SpanKind.CONSUMER,
        attributes=attributes,
        links=links,
    )


def record_failure(err: BaseException) -> None:
    """Record the exception that failed the current attempt on its span.

    Args:
        err: The exception the step raised, or that refused its commit.
    """
    if not enabled:
        return
    span = trace.get_current_span()
    span.record_exception(err)
    span.set_attribute(ATTR_ERROR_TYPE, type(err).__qualname__)


def record_outcome(outcome: str) -> None:
    """Record how the current attempt ended on its span.

    Args:
        outcome: ok, retry, failed, or fenced.
    """
    if not enabled:
        return
    span = trace.get_current_span()
    span.set_attribute(ATTR_OUTCOME, outcome)
    if outcome in _ERROR_OUTCOMES:
        span.set_status(trace.StatusCode.ERROR, outcome)


__all__ = [
    "ATTR_ATTEMPT",
    "ATTR_ERROR_TYPE",
    "ATTR_LANE",
    "ATTR_OUTCOME",
    "ATTR_STEP",
    "ATTR_TABLE",
    "INSTRUMENTATION_NAME",
    "TRACE_KEY",
    "disable",
    "enable",
    "enabled",
    "record_failure",
    "record_outcome",
    "stamp",
    "step_span",
]
