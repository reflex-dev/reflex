"""Benchmarks for per-event ASGI header decoding."""

import pytest
from pytest_codspeed import BenchmarkFixture

from reflex.app import _decode_asgi_headers


@pytest.mark.parametrize("count", [0, 4, 16, 64])
def test_decode_event_headers(count: int, benchmark: BenchmarkFixture):
    """Benchmark the header decoding used by ``EventNamespace.on_event``.

    Args:
        count: Number of headers.
        benchmark: The CodSpeed benchmark fixture.
    """
    headers = [
        (f"x-performance-{index}".encode(), f"value-{index}".encode())
        for index in range(count)
    ]
    decoded = benchmark(lambda: _decode_asgi_headers(headers))
    assert len(decoded) == count
