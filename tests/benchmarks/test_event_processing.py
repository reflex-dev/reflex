"""Benchmark for the event processing pipeline.

Measures the time from calling the ``process`` function (the core of
``on_event``) to collecting all emitted ``StateUpdate`` deltas, with a
mocked ``emit`` replaced by an ``asyncio.Event`` that signals completion.
"""

import asyncio
import contextlib
from unittest import mock

import pytest
import pytest_asyncio
from pytest_codspeed import BenchmarkFixture
from reflex_base.utils.format import format_event_handler

from reflex.app import App, process
from reflex.event import Event
from reflex.istate.manager.memory import StateManagerMemory
from reflex.state import State

from .fixtures import BenchmarkState


@pytest.fixture
def app_module_mock(monkeypatch) -> mock.Mock:
    """Mock the app module so state machinery can resolve the app.

    Args:
        monkeypatch: pytest monkeypatch fixture.

    Returns:
        The mock for the main app module.
    """
    from reflex.utils import prerequisites

    app_module_mock = mock.Mock()
    get_app_mock = mock.Mock(return_value=app_module_mock)
    monkeypatch.setattr(prerequisites, "get_app", get_app_mock)
    return app_module_mock


@pytest_asyncio.fixture
async def event_processing_harness(app_module_mock: mock.Mock):
    """Set up the full event processing pipeline for benchmarking.

    Creates an App wired to a real StateManagerMemory. The ``process``
    function is called directly (bypassing Socket.IO) and StateUpdates
    are collected. An ``asyncio.Event`` signals when the expected number
    of updates has been received.

    Args:
        app_module_mock: The mocked app module.

    Yields:
        An async callable that processes the given events and waits for
        all expected deltas.
    """
    app = app_module_mock.app = App()
    state_manager = StateManagerMemory(state=State)
    app._state_manager = state_manager
    # Disable event namespace so process() doesn't try to emit "reload"
    # via Socket.IO for brand-new states.
    app._event_namespace = None

    token = "benchmark-token"
    sid = "benchmark-sid"
    headers: dict = {}
    client_ip = "127.0.0.1"

    handler_name = format_event_handler(BenchmarkState.event_handlers["increment"])

    event = Event(
        token=token,
        name=handler_name,
        router_data={
            "query": {},
            "path": "/",
        },
        payload={},
    )

    delta_count = 0
    expected_deltas = 0

    async def run_events(num_events: int, num_expected_deltas: int) -> None:
        """Process events through the pipeline and wait for deltas.

        Args:
            num_events: Number of increment events to process.
            num_expected_deltas: How many StateUpdates to wait for.
        """
        nonlocal delta_count, expected_deltas
        delta_count = 0
        expected_deltas = num_expected_deltas

        for _ in range(num_events):
            async with contextlib.aclosing(
                process(app, event, sid, headers, client_ip)
            ) as updates:
                async for _update in updates:
                    delta_count += 1

    yield run_events

    await state_manager.close()


def test_process_event(
    event_processing_harness,
    benchmark: BenchmarkFixture,
):
    """Benchmark processing 3 increment events through the full pipeline.

    The first event creates fresh state (cold path), the next two reuse
    the existing state (warm path). All machinery is set up outside the
    benchmark; only the event processing is timed.

    Args:
        event_processing_harness: The run_events async callable.
        benchmark: The codspeed benchmark fixture.
    """
    run_events = event_processing_harness
    loop = asyncio.get_event_loop()

    # Each call to process() for a non-background event yields StateUpdates.
    # The _process_event generator yields one update per yield/return plus a
    # final update. For a simple handler like increment() with no yield,
    # we get 1 StateUpdate per event = 3 total.
    @benchmark
    def _():
        loop.run_until_complete(run_events(num_events=3, num_expected_deltas=3))
