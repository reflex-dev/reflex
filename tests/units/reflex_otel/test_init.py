"""Tests for the reflex_otel instrumentor."""

from collections.abc import Generator

import pytest
from opentelemetry.sdk.trace import TracerProvider
from reflex_base import otel
from reflex_otel import ReflexInstrumentor


@pytest.fixture
def instrumentor() -> Generator[ReflexInstrumentor, None, None]:
    inst = ReflexInstrumentor()
    yield inst
    if inst._is_instrumented_by_opentelemetry:
        inst.uninstrument()


def test_instrument_toggles_trace_points(instrumentor: ReflexInstrumentor):
    assert otel.enabled is False
    instrumentor.instrument(tracer_provider=TracerProvider())
    assert otel.enabled is True
    instrumentor.uninstrument()
    assert otel.enabled is False


def test_instrument_is_idempotent(instrumentor: ReflexInstrumentor):
    instrumentor.instrument()
    instrumentor.instrument()
    assert otel.enabled is True


def test_dependencies_target_reflex_base(instrumentor: ReflexInstrumentor):
    (dep,) = instrumentor.instrumentation_dependencies()
    assert dep.startswith("reflex-base")
