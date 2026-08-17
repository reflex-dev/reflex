"""Shared fixtures for reflex_base unit tests."""

from collections.abc import Generator

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from reflex_base import otel


@pytest.fixture
def otel_exporter() -> Generator[InMemorySpanExporter, None, None]:
    """Enable the reflex_base.otel trace points against an in-memory exporter.

    Yields:
        The exporter collecting finished spans.
    """
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    otel.enable(tracer_provider=provider)
    try:
        yield exporter
    finally:
        otel.disable()
