"""Tests for the reflex_base.otel trace points."""

import asyncio
from time import perf_counter

import pytest
from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import SpanKind, StatusCode
from reflex_base import otel
from reflex_base.event.context import EventContext
from reflex_base.registry import RegisteredEventHandler

from reflex.event import Event, EventHandler
from tests.units.conftest import metric_points


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
    assert child.kind == SpanKind.INTERNAL


def test_event_span_records_duration_metric(otel_metrics: InMemoryMetricReader):
    registered = RegisteredEventHandler(handler=EventHandler(fn=_handler), states=())
    with otel.event_span(Event(name="ok"), _ctx(), registered):
        pass
    with (
        pytest.raises(RuntimeError),
        otel.event_span(Event(name="bad"), _ctx(), registered),
    ):
        raise RuntimeError
    with (
        pytest.raises(asyncio.CancelledError),
        otel.event_span(Event(name="cancelled"), _ctx(), registered),
    ):
        raise asyncio.CancelledError
    bad, cancelled, ok = sorted(
        metric_points(otel_metrics, otel.METRIC_EVENT_DURATION),
        key=lambda p: p.attributes[otel.ATTR_EVENT_NAME],
    )
    assert otel.ATTR_ERROR_TYPE not in cancelled.attributes
    assert bad.attributes == {
        otel.ATTR_EVENT_NAME: "bad",
        otel.ATTR_EVENT_BACKGROUND: False,
        otel.ATTR_ERROR_TYPE: "RuntimeError",
    }
    assert ok.attributes == {
        otel.ATTR_EVENT_NAME: "ok",
        otel.ATTR_EVENT_BACKGROUND: False,
    }
    assert ok.count == bad.count == 1
    assert ok.sum >= 0


def test_event_duration_recorded_inside_span(
    otel_exporter: InMemorySpanExporter, monkeypatch: pytest.MonkeyPatch
):
    seen: list[trace.Span] = []

    class Histogram:
        def record(self, amount, attributes=None):
            seen.append(trace.get_current_span())

    monkeypatch.setattr(otel, "_event_duration", Histogram())
    registered = RegisteredEventHandler(handler=EventHandler(fn=_handler), states=())
    with otel.event_span(Event(name="ok"), _ctx(), registered) as span:
        pass
    # The sample must be taken while the event span is still current so
    # exporter latency is excluded and exemplars keep the trace/span IDs.
    assert len(seen) == 1
    assert seen[0] is span
    assert seen[0].get_span_context().is_valid


def test_metric_helpers_record(otel_metrics: InMemoryMetricReader):
    otel.record_state_acquired(perf_counter(), Event(name="e"))
    otel.record_message_size(42, "transmit")
    otel.record_connection(1)
    otel.record_connection(1)
    otel.record_connection(-1)
    (acquire,) = metric_points(otel_metrics, otel.METRIC_STATE_ACQUIRE_DURATION)
    assert acquire.attributes == {otel.ATTR_EVENT_NAME: "e"}
    (size,) = metric_points(otel_metrics, otel.METRIC_WEBSOCKET_MESSAGE_SIZE)
    assert size.sum == 42
    assert size.attributes == {otel.ATTR_NETWORK_IO_DIRECTION: "transmit"}
    (conns,) = metric_points(otel_metrics, otel.METRIC_WEBSOCKET_CONNECTIONS)
    assert conns.value == 1


def test_remote_context_uses_traceparent(otel_exporter: InMemorySpanExporter):
    registered = RegisteredEventHandler(handler=EventHandler(fn=_handler), states=())
    traceparent = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
    with otel.remote_context({"traceparent": traceparent}):
        ctx = _ctx().fork()
    with otel.event_span(Event(name="e"), ctx, registered):
        pass
    (span,) = otel_exporter.get_finished_spans()
    assert span.kind == SpanKind.SERVER
    assert span.parent is not None
    assert span.parent.is_remote
    assert format(span.parent.trace_id, "032x") == "0af7651916cd43dd8448eb211c80319c"
    assert format(span.parent.span_id, "016x") == "b7ad6b7169203331"


def test_remote_context_without_traceparent_starts_new_trace(
    otel_exporter: InMemorySpanExporter,
):
    registered = RegisteredEventHandler(handler=EventHandler(fn=_handler), states=())
    with otel._tracer.start_as_current_span("websocket"), otel.remote_context({}):
        ctx = _ctx().fork()
    with otel.event_span(Event(name="e"), ctx, registered):
        pass
    _ws, span = otel_exporter.get_finished_spans()
    assert span.parent is None


def test_asgi_middleware_hook_toggles():
    assert otel.asgi_middleware is None
    factory = lambda app: app  # noqa: E731
    otel.enable(asgi_middleware_factory=factory)
    assert otel.asgi_middleware is factory
    otel.disable()
    assert otel.asgi_middleware is None


def test_attach_context(otel_exporter: InMemorySpanExporter):
    with otel._tracer.start_as_current_span("outer") as outer:
        captured = otel.capture_context()
    otel.attach_context(None)
    assert not trace.get_current_span().get_span_context().is_valid
    token = otel_context.attach(otel_context.get_current())
    try:
        otel.attach_context(captured)
        assert trace.get_current_span() is outer
    finally:
        otel_context.detach(token)
