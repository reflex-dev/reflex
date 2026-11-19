"""Benchmarks for ASGI header decoding on socket connect."""

import pytest
from pytest_codspeed import BenchmarkFixture

from reflex.app import _decode_asgi_headers

# Decoding a request's headers takes a few microseconds, so each measured call
# decodes them this many times.
DECODE_CALLS = 200


@pytest.mark.parametrize("count", [4, 16, 64])
def test_decode_event_headers(count: int, benchmark: BenchmarkFixture):
    """Benchmark the header decoding ``EventNamespace`` does for every connection.

    The decoded headers are cached per socket, so each page load, tab and
    reconnect pays for this once, and the events on that socket reuse it.

    Args:
        count: Number of headers.
        benchmark: The CodSpeed benchmark fixture.
    """
    headers = [
        (f"x-performance-{index}".encode(), f"value-{index}".encode())
        for index in range(count)
    ]
    decoded = benchmark(
        lambda: [_decode_asgi_headers(headers) for _ in range(DECODE_CALLS)]
    )
    assert (
        decoded
        == [{f"x-performance-{index}": f"value-{index}" for index in range(count)}]
        * DECODE_CALLS
    )
