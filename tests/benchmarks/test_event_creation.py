"""Benchmarks for event creation and conversion APIs."""

from typing import Any

import pytest
from pytest_codspeed import BenchmarkFixture
from reflex_base.event import Event, EventHandler, EventSpec

import reflex as rx

from .fixtures import BenchmarkState


def test_console_log(benchmark: BenchmarkFixture):
    """Benchmark creation of an ``rx.console_log`` event spec.

    Args:
        benchmark: The codspeed benchmark fixture.
    """
    benchmark(lambda: rx.console_log("hello"))


@pytest.fixture(scope="module")
def increment_handler() -> EventHandler:
    """The ``increment`` EventHandler from ``BenchmarkState``.

    Returns:
        The state-bound EventHandler used by all ``from_event_type`` benchmarks.
    """
    return BenchmarkState.event_handlers["increment"]


@pytest.fixture(scope="module")
def increment_spec(increment_handler: EventHandler) -> EventSpec:
    """An EventSpec produced by calling the increment EventHandler.

    Args:
        increment_handler: The state-bound EventHandler.

    Returns:
        The EventSpec produced by invoking the handler with no args.
    """
    return increment_handler()


@pytest.fixture(scope="module")
def increment_event(increment_spec: EventSpec) -> Event:
    """An Event built from the increment EventSpec.

    Args:
        increment_spec: The EventSpec for the increment handler.

    Returns:
        The runtime Event derived from the EventSpec.
    """
    return Event.from_event_type(increment_spec)[0]


@pytest.fixture(
    params=(
        "event",
        "event_spec",
        "event_handler",
        "lambda_event",
        "lambda_event_spec",
        "lambda_event_handler",
    )
)
def event_input(
    request: pytest.FixtureRequest,
    increment_event: Event,
    increment_spec: EventSpec,
    increment_handler: EventHandler,
) -> Any:
    """Parametrized event-like input accepted by ``Event.from_event_type``.

    Args:
        request: The pytest fixture request carrying the param id.
        increment_event: The pre-built runtime Event.
        increment_spec: The pre-built EventSpec.
        increment_handler: The state-bound EventHandler.

    Returns:
        One of the supported input shapes for ``Event.from_event_type``.

    Raises:
        ValueError: If the parametrized value is unrecognized.
    """
    inputs: dict[str, Any] = {
        "event": increment_event,
        "event_spec": increment_spec,
        "event_handler": increment_handler,
        "lambda_event": lambda: increment_event,
        "lambda_event_spec": lambda: increment_spec,
        "lambda_event_handler": lambda: increment_handler,
    }
    return inputs[request.param]


def test_from_event_type(event_input: Any, benchmark: BenchmarkFixture):
    """Benchmark ``Event.from_event_type`` for each supported input shape.

    Covers existing Event, EventSpec (from calling EventHandler), EventHandler,
    and lambdas returning each of those — the common shapes encountered
    when normalizing user-returned event values.

    Args:
        event_input: The parametrized event-like input.
        benchmark: The codspeed benchmark fixture.
    """
    benchmark(lambda: Event.from_event_type(event_input))
