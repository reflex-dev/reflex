"""Benchmarks for chained-event payload snapshotting."""

from typing import Any

from pytest_codspeed import BenchmarkFixture

from reflex.event import Event, EventHandler

from .support.states import initialized_state


def _receive_payload(payload: Any) -> None:
    """Define a handler accepting arbitrary representative payloads.

    Args:
        payload: Event payload.
    """


PAYLOAD_EVENT = EventHandler(fn=_receive_payload)


def test_event_payload_plain_collection(benchmark: BenchmarkFixture):
    """Benchmark snapshotting a large proxy-free event payload.

    Args:
        benchmark: The CodSpeed benchmark fixture.
    """
    payload = [{"index": index, "label": f"row-{index}"} for index in range(10_000)]
    events = benchmark(lambda: Event.from_event_type(PAYLOAD_EVENT(payload)))
    assert len(events[0].payload["payload"]) == len(payload)


def test_event_payload_mutable_proxy(benchmark: BenchmarkFixture):
    """Benchmark the required detachment of a state-bound mutable proxy.

    Args:
        benchmark: The CodSpeed benchmark fixture.
    """
    state = initialized_state(10_000)
    payload = state.numbers
    events = benchmark(lambda: Event.from_event_type(PAYLOAD_EVENT(payload)))
    assert events[0].payload["payload"] == list(range(10_000))
