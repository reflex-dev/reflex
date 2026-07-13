"""Benchmarks for per-event ASGI header decoding."""

import pytest
from pytest_codspeed import BenchmarkFixture


@pytest.mark.parametrize("count", [0, 4, 16, 64])
def test_decode_event_headers(count: int, benchmark: BenchmarkFixture):
    """Benchmark decoding the ASGI header representation used by socket events.

    Args:
        count: Number of headers.
        benchmark: The CodSpeed benchmark fixture.
    """
    headers = [
        (f"x-performance-{index}".encode(), f"value-{index}".encode())
        for index in range(count)
    ]
    decoded = benchmark(
        lambda: {key.decode("utf-8"): value.decode("utf-8") for key, value in headers}
    )
    assert len(decoded) == count
