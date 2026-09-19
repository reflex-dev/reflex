"""SDK wiring for the otel prerelease test app.

Imported once by the app module. Writes every finished span and every metric
export to newline-delimited JSON under $OTEL_DUMP_DIR, one file per process.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

DUMP_DIR = Path(os.environ.get("OTEL_DUMP_DIR", "/tmp/otel-dump"))
DUMP_DIR.mkdir(parents=True, exist_ok=True)


def _dump(kind: str) -> Path:
    return DUMP_DIR / f"{kind}-{os.getpid()}.jsonl"


class JsonlSpanExporter:
    """Write each finished span as one compact JSON line."""

    def __init__(self, path: Path):
        self.path = path

    def export(self, spans):  # noqa: D102
        from opentelemetry.sdk.trace.export import SpanExportResult

        with self.path.open("a") as f:
            for span in spans:
                f.write(json.dumps(json.loads(span.to_json())) + "\n")
            f.flush()
            os.fsync(f.fileno())
        return SpanExportResult.SUCCESS

    def shutdown(self):  # noqa: D102
        return None

    def force_flush(self, timeout_millis: int = 30000):  # noqa: D102
        return True


class JsonlMetricExporter:
    """Write each metric export batch as one compact JSON line."""

    def __init__(self, path: Path):
        from opentelemetry.sdk.metrics.export import (
            AggregationTemporality,
        )
        from opentelemetry.sdk.metrics import Counter, Histogram, ObservableCounter
        from opentelemetry.sdk.metrics import ObservableGauge, ObservableUpDownCounter
        from opentelemetry.sdk.metrics import UpDownCounter

        self.path = path
        self._preferred_temporality = {
            Counter: AggregationTemporality.CUMULATIVE,
            UpDownCounter: AggregationTemporality.CUMULATIVE,
            Histogram: AggregationTemporality.CUMULATIVE,
            ObservableCounter: AggregationTemporality.CUMULATIVE,
            ObservableUpDownCounter: AggregationTemporality.CUMULATIVE,
            ObservableGauge: AggregationTemporality.CUMULATIVE,
        }
        self._preferred_aggregation = {}

    def export(self, metrics_data, timeout_millis: float = 10_000, **kwargs: Any):  # noqa: D102
        from opentelemetry.sdk.metrics.export import MetricExportResult

        with self.path.open("a") as f:
            f.write(metrics_data.to_json(indent=None) + "\n")
            f.flush()
            os.fsync(f.fileno())
        return MetricExportResult.SUCCESS

    def shutdown(self, timeout_millis: float = 30_000, **kwargs: Any):  # noqa: D102
        return None

    def force_flush(self, timeout_millis: float = 10_000):  # noqa: D102
        return True


TRACER_PROVIDER = None
METER_PROVIDER = None


def setup() -> tuple[Any, Any]:
    """Build and install SDK providers, then instrument reflex."""
    global TRACER_PROVIDER, METER_PROVIDER
    if TRACER_PROVIDER is not None:
        return TRACER_PROVIDER, METER_PROVIDER

    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create({"service.name": os.environ.get("OTEL_SERVICE_NAME", "otelapp")})
    TRACER_PROVIDER = TracerProvider(resource=resource)
    TRACER_PROVIDER.add_span_processor(
        BatchSpanProcessor(
            JsonlSpanExporter(_dump("spans")),
            schedule_delay_millis=500,
            max_export_batch_size=64,
        )
    )
    METER_PROVIDER = MeterProvider(
        resource=resource,
        metric_readers=[
            PeriodicExportingMetricReader(
                JsonlMetricExporter(_dump("metrics")),
                export_interval_millis=2000,
            )
        ],
    )
    print(f"[telemetry] pid={os.getpid()} argv={sys.argv} dump={DUMP_DIR}", flush=True)
    return TRACER_PROVIDER, METER_PROVIDER
