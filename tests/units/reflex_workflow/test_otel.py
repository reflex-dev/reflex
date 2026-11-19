"""Tests for the reflex_workflow.otel trace points."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Generator

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, StatusCode
from reflex_workflow import otel, step
from reflex_workflow.model import Call


@pytest.fixture
def exporter() -> Generator[InMemorySpanExporter, None, None]:
    """Enable the trace points against an in-memory exporter.

    Yields:
        The exporter.
    """
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    otel.enable(tracer_provider=provider)
    try:
        yield exporter
    finally:
        otel.disable()


@pytest.fixture
def tracer(exporter: InMemorySpanExporter) -> trace.Tracer:
    """A tracer on the enabled provider, for spans standing in for the app's.

    Args:
        exporter: The enabled exporter.

    Returns:
        The tracer.
    """
    return otel._tracer


async def _noop(self) -> None:
    """A step body that does nothing."""


def _ids(context: trace.SpanContext | None) -> tuple[int, int]:
    """The identity of a span context, without the remote flag a link sets.

    Args:
        context: The span context.

    Returns:
        Its trace and span ids.
    """
    assert context is not None
    return context.trace_id, context.span_id


def test_disabled_path_imports_no_opentelemetry():
    """reflex-workflow does not depend on opentelemetry-api; nothing loads it until enable()."""
    code = (
        "import sys; import reflex_workflow; "
        "from reflex_workflow import otel; from reflex_workflow.model import Call; "
        "print(sorted(m for m in sys.modules if m.startswith('opentelemetry')))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], check=True, capture_output=True, text=True
    )
    assert out.stdout.strip() == "[]"


def test_disabled_trace_points_change_nothing():
    assert otel.enabled is False
    payload = {"args": [1], "kwargs": {}}
    assert otel.stamp(payload) is payload
    assert payload == {"args": [1], "kwargs": {}}
    with otel.step_span("t", "s", 1, "default", None) as span:
        assert span is None
        otel.record_failure(ValueError("x"))
        otel.record_outcome("failed")
    assert trace.get_current_span().get_span_context().is_valid is False


def test_enable_twice_keeps_the_first_tracer(exporter: InMemorySpanExporter):
    tracer = otel._tracer
    otel.enable(tracer_provider=TracerProvider())
    assert otel._tracer is tracer


def test_stamp_writes_the_current_span_and_encode_carries_it(tracer: trace.Tracer):
    assert otel.stamp({"args": []}) == {"args": []}
    call = Call(step(_noop), (), {})
    with tracer.start_as_current_span("producer") as producer:
        payload = call.encode()
        ctx = producer.get_span_context()
    traceparent = payload.pop(otel.TRACE_KEY)
    assert payload == {"args": [], "kwargs": {}}
    assert (
        traceparent
        == f"00-{ctx.trace_id:032x}-{ctx.span_id:016x}-{ctx.trace_flags:02x}"
    )


def test_step_span_is_a_root_linked_to_its_producer(
    exporter: InMemorySpanExporter, tracer: trace.Tracer
):
    with tracer.start_as_current_span("producer"):
        traceparent = otel.stamp({})[otel.TRACE_KEY]
    # Entered under an unrelated span, as a worker inherits one from its lifespan.
    with (
        tracer.start_as_current_span("inherited") as inherited,
        otel.step_span("expense", "submit", 2, "media", traceparent) as span,
    ):
        assert span is not None
        assert trace.get_current_span() is span
        otel.record_outcome("ok")
    producer, step, _ = exporter.get_finished_spans()
    assert step.name == "expense.submit"
    assert step.kind is SpanKind.CONSUMER
    assert step.parent is None
    assert _ids(step.get_span_context())[0] != inherited.get_span_context().trace_id
    assert [_ids(link.context) for link in step.links] == [_ids(producer.context)]
    assert step.attributes == {
        otel.ATTR_TABLE: "expense",
        otel.ATTR_STEP: "submit",
        otel.ATTR_ATTEMPT: 2,
        otel.ATTR_LANE: "media",
        otel.ATTR_OUTCOME: "ok",
    }
    assert step.status.status_code is StatusCode.UNSET


@pytest.mark.parametrize(
    "traceparent", [None, 42, "garbage", "00-" + "0" * 32 + "-" + "0" * 16 + "-01"]
)
def test_step_span_without_a_usable_producer_has_no_link(
    exporter: InMemorySpanExporter, traceparent: object
):
    with otel.step_span("expense", "submit", 1, None, traceparent):
        pass
    (step,) = exporter.get_finished_spans()
    assert step.links == ()
    assert otel.ATTR_LANE not in (step.attributes or {})


@pytest.mark.parametrize("outcome", ["retry", "failed"])
def test_failed_attempt_records_the_error(exporter: InMemorySpanExporter, outcome: str):
    with otel.step_span("expense", "submit", 1, "default", None):
        otel.record_failure(ConnectionError("provider timed out"))
        otel.record_outcome(outcome)
    (step,) = exporter.get_finished_spans()
    assert step.status.status_code is StatusCode.ERROR
    assert step.status.description == outcome
    assert step.attributes is not None
    assert step.attributes[otel.ATTR_ERROR_TYPE] == "ConnectionError"
    assert step.attributes[otel.ATTR_OUTCOME] == outcome
    (event,) = step.events
    assert event.name == "exception"
    assert event.attributes is not None
    assert event.attributes["exception.type"] == "ConnectionError"
