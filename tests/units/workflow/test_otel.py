"""The OpenTelemetry observer, driven by real runs through a real SDK.

Exported against the SDK's in-memory exporter and reader rather than a mock,
because the questions worth asking are whether a span actually ends, whether
its status survives a failure, and whether the counters agree with the
non-OpenTelemetry exporter -- none of which a mock can answer.
"""

import pytest
from reflex_base.workflow import Retry, TransientWorkflowError, WorkflowConfig, manual

import reflex as rx
from reflex.workflow.kernel import CompositeObserver, MetricsObserver
from reflex.workflow.testing import WorkflowTestHarness

pytest.importorskip("opentelemetry", reason="OpenTelemetry is an optional extra")

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from reflex.workflow.otel import OpenTelemetryObserver


class Charge(rx.State):
    """One good step and one that fails for good."""

    __workflow__ = WorkflowConfig(id="otel.charge")
    amount: int = 0

    @rx.event(durable=True, trigger=manual(), effect="none")
    def go(self, amount: int):
        """Succeed.

        Args:
            amount: The amount to record.

        Returns:
            Completion.
        """
        self.amount = amount
        return rx.complete(result={"amount": amount})

    @rx.event(
        durable=True, trigger=manual(), effect="none", retry=Retry(max_attempts=1)
    )
    def doomed(self):
        """Fail.

        Raises:
            TransientWorkflowError: Always.
        """
        msg = "vendor down"
        raise TransientWorkflowError(msg)


@pytest.fixture
def otel():
    """Wire an observer to in-memory span and metric collectors.

    Returns:
        The observer, the span exporter, and the metric reader.
    """
    exporter = InMemorySpanExporter()
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))
    reader = InMemoryMetricReader()
    observer = OpenTelemetryObserver(
        tracer_provider=tracer_provider,
        meter_provider=MeterProvider(metric_readers=[reader]),
    )
    return observer, exporter, reader


def _counter(reader, name: str) -> int:
    """Total one counter across its attribute sets.

    Args:
        reader: The in-memory metric reader.
        name: The counter's full name.

    Returns:
        The summed value, or zero when the counter never fired.
    """
    total = 0
    data = reader.get_metrics_data()
    for resource in data.resource_metrics if data else ():
        for scope in resource.scope_metrics:
            for metric in scope.metrics:
                if metric.name == name:
                    total += sum(point.value for point in metric.data.data_points)
    return total


async def test_a_successful_attempt_becomes_one_ok_span(
    otel, forked_registration_context
):
    """The span names the handler and carries the run it belongs to.

    Args:
        otel: The observer and its collectors.
        forked_registration_context: Isolates workflow registration.
    """
    observer, exporter, _ = otel
    async with WorkflowTestHarness(Charge, observer=observer) as harness:
        started = await harness.start(Charge.go(2500))
        assert started.run_id is not None

    spans = exporter.get_finished_spans()
    assert len(spans) == 1, [span.name for span in spans]
    span = spans[0]
    assert span.name == "otel.charge.go"
    assert span.attributes["workflow.run_id"] == started.run_id
    assert span.attributes["workflow.handler_id"] == "go"
    assert span.attributes["workflow.attempt"] == 1
    assert span.attributes["workflow.attempt_outcome"] == "succeeded"
    assert span.status.is_ok


async def test_a_failed_attempt_ends_its_span_with_an_error(
    otel, forked_registration_context
):
    """A span left open would be worse than no span at all.

    Args:
        otel: The observer and its collectors.
        forked_registration_context: Isolates workflow registration.
    """
    observer, exporter, _ = otel
    async with WorkflowTestHarness(Charge, observer=observer) as harness:
        await harness.start(Charge.doomed())

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].attributes["workflow.attempt_outcome"] == "failed"
    assert not spans[0].status.is_ok


async def test_the_counters_agree_with_the_other_exporter(
    otel, forked_registration_context
):
    """Two exporters that disagree about one deployment are worse than one.

    Args:
        otel: The observer and its collectors.
        forked_registration_context: Isolates workflow registration.
    """
    observer, _, reader = otel
    metrics_observer = MetricsObserver()
    both = CompositeObserver(observer, metrics_observer)
    async with WorkflowTestHarness(Charge, observer=both) as harness:
        await harness.start(Charge.go(1))
        await harness.start(Charge.go(2))
        await harness.start(Charge.doomed())

    for name, expected in (
        ("runs_started", 3),
        ("runs_completed", 2),
        ("runs_failed", 1),
        ("attempts", 3),
    ):
        assert metrics_observer.totals.get(name, 0) == expected, name
        assert _counter(reader, f"reflex.workflow.{name}") == expected, name


def test_dead_letters_are_counted_by_both_exporters(otel):
    """A lost delivery must show up in whichever exporter the deployment reads.

    Args:
        otel: The observer and its collectors.
    """
    observer, _, reader = otel
    metrics_observer = MetricsObserver()
    both = CompositeObserver(observer, metrics_observer)
    both.on_dead_letter("orders", "shipped", 2, "undeliverable")
    both.on_dead_letter(None, None, 3, "unclaimed")

    assert metrics_observer.totals["deliveries_dead_lettered"] == 5
    assert _counter(reader, "reflex.workflow.deliveries_dead_lettered") == 5
