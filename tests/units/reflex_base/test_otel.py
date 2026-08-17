"""Tests for the reflex_base.otel trace points."""

import pytest
from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, StatusCode
from reflex_base import otel
from reflex_base.event.context import EventContext
from reflex_base.registry import RegisteredEventHandler

from reflex.event import Event, EventHandler


def _ctx(token: str = "tok", parent_txid: str | None = None) -> EventContext:
    return EventContext(
        token=token,
        state_manager=None,  # type: ignore[arg-type]
        enqueue_impl=None,  # type: ignore[arg-type]
        parent_txid=parent_txid,
    )


async def _handler():
    """A no-op handler."""


def test_disabled_by_default():
    assert otel.enabled is False
    assert otel.capture_context() is None


def test_enable_disable_toggle():
    otel.enable()
    assert otel.enabled is True
    assert otel.capture_context() is not None
    otel.disable()
    assert otel.enabled is False
    assert isinstance(otel._tracer, trace.NoOpTracer)


def test_capture_context_returns_current(otel_exporter: InMemorySpanExporter):
    with otel._tracer.start_as_current_span("outer") as span:
        captured = otel.capture_context()
    assert captured is not None
    assert trace.get_current_span(captured) is span
    assert otel_context.get_current() is not captured


def test_event_span_attributes(otel_exporter: InMemorySpanExporter):
    ctx = _ctx(parent_txid="parent123")
    event = Event(name="state.sub.handler")
    registered = RegisteredEventHandler(handler=EventHandler(fn=_handler), states=())
    with otel.event_span(event, ctx, registered) as span:
        assert trace.get_current_span() is span
    (finished,) = otel_exporter.get_finished_spans()
    assert finished.name == "state.sub.handler"
    assert finished.kind == SpanKind.SERVER
    assert finished.parent is None
    assert finished.attributes == {
        otel.ATTR_EVENT_NAME: "state.sub.handler",
        otel.ATTR_EVENT_TXID: ctx.txid,
        otel.ATTR_EVENT_PARENT_TXID: "parent123",
        otel.ATTR_EVENT_BACKGROUND: False,
        otel.ATTR_SESSION_ID: "tok",
        otel.ATTR_CODE_FUNCTION_NAME: "_handler",
    }
    assert finished.status.status_code == StatusCode.UNSET


def test_event_span_records_exception(otel_exporter: InMemorySpanExporter):
    registered = RegisteredEventHandler(handler=EventHandler(fn=_handler), states=())
    with (
        pytest.raises(RuntimeError, match="boom"),
        otel.event_span(Event(name="e"), _ctx(), registered),
    ):
        msg = "boom"
        raise RuntimeError(msg)
    (finished,) = otel_exporter.get_finished_spans()
    assert finished.status.status_code == StatusCode.ERROR
    assert finished.events[0].name == "exception"


def test_event_span_parents_under_captured_context(
    otel_exporter: InMemorySpanExporter,
):
    registered = RegisteredEventHandler(handler=EventHandler(fn=_handler), states=())
    with otel._tracer.start_as_current_span("root") as root:
        child_ctx = _ctx().fork()
    assert child_ctx.otel_context is not None
    with otel.event_span(Event(name="child"), child_ctx, registered):
        pass
    _root, child = otel_exporter.get_finished_spans()
    assert child.parent is not None
    assert child.parent.span_id == root.get_span_context().span_id
