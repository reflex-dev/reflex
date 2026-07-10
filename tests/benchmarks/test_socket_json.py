"""Benchmarks for the outgoing socket JSON encoder.

Encodes the same large state-update packet with the stdlib-based encoder
and with the wire encoder (orjson fast path), so the two absolute timings
can be compared directly in the report.
"""

from pytest_codspeed import BenchmarkFixture
from reflex_base.utils import format

from reflex.app import _socket_json_dumps

# A realistic large delta: one update packet carrying 2k rows of mixed data.
_LARGE_PACKET = [
    "event",
    {
        "delta": {
            "app.state": {
                "rows": [
                    {
                        "id": i,
                        "name": f"row {i}",
                        "score": i * 1.5,
                        "active": i % 2 == 0,
                        "tags": ["alpha", "beta", "gamma"],
                    }
                    for i in range(2000)
                ],
            },
        },
    },
]


def test_socket_json_dumps_stdlib(benchmark: BenchmarkFixture):
    """Benchmark the stdlib encoder on a large update packet.

    Args:
        benchmark: The codspeed benchmark fixture.
    """
    benchmark(lambda: format.json_dumps(_LARGE_PACKET, separators=(",", ":")))


def test_socket_json_dumps_wire(benchmark: BenchmarkFixture):
    """Benchmark the wire encoder (orjson fast path) on the same packet.

    Args:
        benchmark: The codspeed benchmark fixture.
    """
    benchmark(lambda: _socket_json_dumps(_LARGE_PACKET))
