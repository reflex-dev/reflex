"""Opt-in pytest fixtures shared by Reflex unit suites.

Import the fixtures a suite needs explicitly in its conftest.py. Importing
reflex.testing alone does not require pytest or register any fixtures.
"""

import traceback
import uuid
from collections.abc import AsyncGenerator, Generator, Mapping
from typing import Any
from unittest import mock

import pytest
import pytest_asyncio
from opentelemetry import trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from reflex_base import otel
from reflex_base.event import Event
from reflex_base.event.context import EventContext
from reflex_base.event.processor import BaseStateEventProcessor
from reflex_base.registry import RegistrationContext

from reflex.istate.manager.memory import StateManagerMemory
from reflex.utils import prerequisites


@pytest.fixture(autouse=True)
def _isolate_app_in_context() -> Generator[None, None, None]:
    """Reset the App slot on the active RegistrationContext between tests.

    A RegistrationContext can only host one App instance, but unit tests
    repeatedly instantiate `rx.App`, so we clear `_app` around each test
    while keeping other registrations shared (matching prior behavior).

    Yields:
        None.
    """
    ctx = RegistrationContext.ensure_context()
    object.__setattr__(ctx, "_app", None)
    yield
    object.__setattr__(ctx, "_app", None)


@pytest.fixture
def app_module_mock(monkeypatch: pytest.MonkeyPatch) -> mock.Mock:
    """Mock the app module.

    This overwrites prerequisites.get_app to return the mock for the app module.

    To use this in your test, assign `app_module_mock.app = rx.App(...)`.

    Args:
        monkeypatch: pytest monkeypatch fixture.

    Returns:
        The mock for the main app module.
    """
    app_module_mock = mock.Mock()
    get_app_mock = mock.Mock(return_value=app_module_mock)
    monkeypatch.setattr(prerequisites, "get_app", get_app_mock)
    return app_module_mock


@pytest.fixture
def token() -> str:
    """Create a token.

    Returns:
        A fresh/unique token string.
    """
    return str(uuid.uuid4())


@pytest.fixture
def mock_base_state_event_processor_obj(
    monkeypatch: pytest.MonkeyPatch,
) -> BaseStateEventProcessor:
    """Create a BaseState event processor.

    Args:
        monkeypatch: pytest monkeypatch fixture.

    Returns:
        A fresh BaseState event processor.
    """
    monkeypatch.setattr(BaseStateEventProcessor, "_rehydrate", mock.AsyncMock())

    def handle_backend_exception(ex: Exception) -> None:
        formatted_exc = "\n".join(traceback.format_exception(ex))
        pytest.fail(f"Event processor raised an unexpected exception:\n{formatted_exc}")

    return BaseStateEventProcessor(
        backend_exception_handler=handle_backend_exception, graceful_shutdown_timeout=1
    )


@pytest.fixture
def emitted_deltas() -> list[tuple[str, Mapping[str, Mapping[str, Any]]]]:
    """Create a list to store emitted deltas.

    Returns:
        A list to store emitted deltas.
    """
    return []


@pytest.fixture
def emitted_events() -> list[tuple[str, tuple[Event, ...]]]:
    """Create a list to store emitted events.

    Returns:
        A list to store emitted events.
    """
    return []


@pytest_asyncio.fixture
async def mock_root_event_context(
    mock_base_state_event_processor_obj: BaseStateEventProcessor,
    emitted_deltas: list[tuple[str, Mapping[str, Mapping[str, Any]]]],
    emitted_events: list[tuple[str, tuple[Event, ...]]],
) -> AsyncGenerator[EventContext]:
    """Create a mock event context.

    Args:
        mock_base_state_event_processor_obj: The mock event processor to use for the context's enqueue implementation.
        emitted_deltas: The list to store emitted deltas.
        emitted_events: The list to store emitted events.

    Yields:
        A mock event context.
    """

    async def emit_delta_impl(  # noqa: RUF029
        token: str, delta: Mapping[str, Mapping[str, Any]]
    ) -> None:
        """Mock emit delta implementation that records emitted deltas.

        Args:
            token: The client token to emit the delta to.
            delta: The delta to emit.
        """
        emitted_deltas.append((token, delta))

    async def emit_event_impl(token: str, *events: Event) -> None:  # noqa: RUF029
        """Mock emit event implementation that records emitted events.

        Args:
            token: The client token to emit the events to.
            events: The events to emit.
        """
        emitted_events.append((token, events))

    state_manager = StateManagerMemory()
    yield EventContext(
        token="",
        state_manager=state_manager,
        enqueue_impl=mock_base_state_event_processor_obj.enqueue_many,
        emit_delta_impl=emit_delta_impl,
        emit_event_impl=emit_event_impl,
    )
    await state_manager.close()


@pytest.fixture
def forked_registration_context() -> Generator[RegistrationContext, None, None]:
    """Fork the registration context and attach it.

    Sets the forked context as the current registration context for the duration
    of the test, then resets it afterwards.

    Yields:
        The forked RegistrationContext.
    """
    with RegistrationContext.get().fork() as ctx:
        yield ctx


@pytest.fixture
def clean_registration_context() -> Generator[RegistrationContext, None, None]:
    """Create and attach a clean registration context.

    Sets the new context as the current registration context for the duration
    of the test, then resets it afterwards.

    Yields:
        The clean RegistrationContext.
    """
    with RegistrationContext() as ctx:
        yield ctx


@pytest.fixture
def otel_sdk() -> Generator[
    tuple[InMemorySpanExporter, InMemoryMetricReader], None, None
]:
    """Enable the reflex_base.otel trace points and metrics against in-memory sinks.

    Yields:
        The span exporter and the metric reader.
    """
    exporter = InMemorySpanExporter()
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))
    reader = InMemoryMetricReader()
    otel.enable(
        tracer_provider=tracer_provider,
        meter_provider=MeterProvider(metric_readers=[reader]),
    )
    try:
        yield exporter, reader
    finally:
        otel.disable()


@pytest.fixture
def otel_exporter(
    otel_sdk: tuple[InMemorySpanExporter, InMemoryMetricReader],
) -> InMemorySpanExporter:
    """The in-memory span exporter of the enabled otel_sdk.

    Args:
        otel_sdk: The enabled sinks.

    Returns:
        The span exporter.
    """
    return otel_sdk[0]


@pytest.fixture
def otel_metrics(
    otel_sdk: tuple[InMemorySpanExporter, InMemoryMetricReader],
) -> InMemoryMetricReader:
    """The in-memory metric reader of the enabled otel_sdk.

    Args:
        otel_sdk: The enabled sinks.

    Returns:
        The metric reader.
    """
    return otel_sdk[1]


def active_tracer() -> trace.Tracer:
    """The tracer bound by the enabled otel_sdk fixture.

    Returns:
        The tracer.
    """
    return otel._tracer


def metric_points(reader: InMemoryMetricReader, name: str) -> list:
    """Collect the data points recorded for one metric.

    Args:
        reader: The in-memory reader to collect from.
        name: The metric name.

    Returns:
        The data points, in recording order.
    """
    data = reader.get_metrics_data()
    assert data is not None
    return [
        point
        for rm in data.resource_metrics
        for sm in rm.scope_metrics
        for metric in sm.metrics
        if metric.name == name
        for point in metric.data.data_points
    ]
