"""Tests for the reflex_base.otel trace points."""

import asyncio
import dis
import inspect
import subprocess
import sys
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
from tests.units.conftest import active_tracer, metric_points


def _ctx(token: str = "tok", parent_txid: str | None = None) -> EventContext:
    return EventContext(
        token=token,
        state_manager=None,  # type: ignore[arg-type]
        enqueue_impl=None,  # type: ignore[arg-type]
        parent_txid=parent_txid,
    )


async def _handler():
    """A no-op handler."""


def test_disabled_path_imports_no_opentelemetry():
    """reflex-base does not depend on opentelemetry-api; nothing loads it until enable()."""
    code = (
        "import sys; import reflex_base.otel; import reflex_base.event.context; "
        "print(sorted(m for m in sys.modules if m.startswith('opentelemetry')))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], check=True, capture_output=True, text=True
    )
    assert out.stdout.strip() == "[]"


def test_trace_points_carry_no_import_statement():
    """The per-event trace points do not pay for an import lookup on every call.

    enable() binds the API modules once; an import statement inside a trace
    point would still cost a ``sys.modules`` lookup after the module is loaded.
    """
    trace_points = (
        otel.capture_context,
        otel.attach_context,
        otel.remote_context,
        inspect.unwrap(otel.event_span),
        otel._AttachedContext.__enter__,
        otel._AttachedContext.__exit__,
        otel.record_state_acquired,
        otel.record_message_size,
        otel.record_connection,
    )
    for trace_point in trace_points:
        opnames = {inst.opname for inst in dis.get_instructions(trace_point)}
        assert "IMPORT_NAME" not in opnames, trace_point.__qualname__


def test_disabled_by_default():
    assert otel.enabled is False
    assert otel.capture_context() is None


def test_enable_disable_toggle():
    otel.enable()
    assert otel.enabled is True
    assert otel.capture_context() is not None
    otel.disable()
    assert otel.enabled is False
    assert otel.capture_context() is None


def test_enable_is_idempotent_until_disabled():
    """A second enable() keeps the first providers; disable() resets."""
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor

    first, second = InMemorySpanExporter(), InMemorySpanExporter()
    providers = []
    for exporter in (first, second):
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        providers.append(provider)
    try:
        otel.enable(tracer_provider=providers[0])
        otel.enable(tracer_provider=providers[1])
        with active_tracer().start_as_current_span("x"):
            pass
        assert len(first.get_finished_spans()) == 1
        assert second.get_finished_spans() == ()
    finally:
        otel.disable()
    assert otel.enabled is False


def test_capture_context_returns_current(otel_exporter: InMemorySpanExporter):
    with active_tracer().start_as_current_span("outer") as span:
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
    assert finished.kind == SpanKind.CONSUMER
    assert finished.parent is None
    assert finished.attributes == {
        otel.ATTR_EVENT_NAME: "state.sub.handler",
        otel.ATTR_EVENT_TXID: ctx.txid,
        otel.ATTR_EVENT_BACKGROUND: False,
        otel.ATTR_SESSION_ID: otel._session_id("tok"),
        otel.ATTR_CODE_FUNCTION_NAME: f"{__name__}._handler",
    }
    assert finished.status.status_code == StatusCode.UNSET


def test_session_id_is_not_the_token():
    """The token authorizes state access; only a stable digest is exported."""
    digest = otel._session_id("secret-token")
    assert "secret-token" not in digest
    assert len(digest) == 16
    assert digest == otel._session_id("secret-token")
    assert digest != otel._session_id("other-token")


def test_parent_txid_only_for_chained_events(otel_exporter: InMemorySpanExporter):
    """Top-level events are forked from the root context; its txid is noise."""
    registered = RegisteredEventHandler(handler=EventHandler(fn=_handler), states=())
    traceparent = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
    with otel.remote_context({"traceparent": traceparent}):
        remote_ctx = _ctx().fork()
    with otel.event_span(Event(name="top"), remote_ctx, registered):
        chained_ctx = _ctx().fork()
    with otel.event_span(Event(name="chained"), chained_ctx, registered):
        pass
    top, chained = otel_exporter.get_finished_spans()
    assert top.attributes is not None
    assert chained.attributes is not None
    assert otel.ATTR_EVENT_PARENT_TXID not in top.attributes
    assert chained.attributes[otel.ATTR_EVENT_PARENT_TXID] == chained_ctx.parent_txid


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
    with active_tracer().start_as_current_span("root") as root:
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
    assert span.kind == SpanKind.CONSUMER
    assert span.parent is not None
    assert span.parent.is_remote
    assert format(span.parent.trace_id, "032x") == "0af7651916cd43dd8448eb211c80319c"
    assert format(span.parent.span_id, "016x") == "b7ad6b7169203331"


@pytest.mark.parametrize(
    "carrier",
    [
        {"traceparent": 123},
        {"traceparent": None},
        {"traceparent": ["a"]},
        {"traceparent": {"x": 1}},
        {"traceparent": "garbage"},
        {"traceparent": "00-" + "0" * 32 + "-b7ad6b7169203331-01"},
        {
            "traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01",
            "tracestate": 5,
        },
        {
            "traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01",
            "tracestate": "==,,bad",
        },
        {"baggage": 7},
    ],
)
def test_remote_context_never_raises_on_unusable_fields(
    carrier: dict, otel_exporter: InMemorySpanExporter
):
    """Hostile or malformed payload fields are ignored, never an exception."""
    registered = RegisteredEventHandler(handler=EventHandler(fn=_handler), states=())
    with otel.remote_context(carrier):
        ctx = _ctx().fork()
    with otel.event_span(Event(name="e"), ctx, registered):
        pass
    (span,) = otel_exporter.get_finished_spans()
    if (
        isinstance(carrier.get("traceparent"), str)
        and "0af7651916cd" in carrier["traceparent"]
    ):
        assert span.parent is not None
        assert (
            format(span.parent.trace_id, "032x") == "0af7651916cd43dd8448eb211c80319c"
        )
    else:
        assert span.parent is None


def test_remote_context_ignores_baggage(otel_exporter: InMemorySpanExporter):
    """Only the trace context is taken from the client, never baggage."""
    from opentelemetry import baggage

    with otel.remote_context({"baggage": "user=admin,tenant=evil"}):
        assert baggage.get_all() == {}


def test_remote_context_without_traceparent_starts_new_trace(
    otel_exporter: InMemorySpanExporter,
):
    registered = RegisteredEventHandler(handler=EventHandler(fn=_handler), states=())
    with active_tracer().start_as_current_span("websocket"), otel.remote_context({}):
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
    with active_tracer().start_as_current_span("outer") as outer:
        captured = otel.capture_context()
    otel.attach_context(None)
    assert not trace.get_current_span().get_span_context().is_valid
    token = otel_context.attach(otel_context.get_current())
    try:
        otel.attach_context(captured)
        assert trace.get_current_span() is outer
    finally:
        otel_context.detach(token)
