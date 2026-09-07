"""Benchmarks for encoding a state delta for the wire.

``json_dumps_compact`` encodes every delta emitted over the websocket; the
payload mixes plain containers with dataclasses that go through the reflex
serializers.
"""

import dataclasses

import pytest
from pytest_codspeed import BenchmarkFixture
from reflex_base.utils.format import json_dumps, json_dumps_compact

N = 10_000


@dataclasses.dataclass
class _Row:
    name: str
    qty: int
    price: float


_ROWS = [_Row(f"row {i}", i, i * 1.5) for i in range(N)]
_DICTS = [{"name": f"row {i}", "qty": i, "price": i * 1.5} for i in range(N)]


@pytest.mark.parametrize(
    "payload",
    [pytest.param(_ROWS, id="dataclasses"), pytest.param(_DICTS, id="dicts")],
)
def test_json_dumps_compact(payload: list, benchmark: BenchmarkFixture):
    """Benchmark the wire encoder on a large delta.

    Args:
        payload: The delta value to encode.
        benchmark: The codspeed benchmark fixture.
    """
    benchmark(lambda: json_dumps_compact({"state": {"rows": payload}}))


def test_json_dumps_reference(benchmark: BenchmarkFixture):
    """Benchmark the stdlib-backed encoder on the same delta for comparison.

    Args:
        benchmark: The codspeed benchmark fixture.
    """
    benchmark(lambda: json_dumps({"state": {"rows": _ROWS}}))
