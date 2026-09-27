"""Benchmarks for state-update and wire serialization."""

import pytest
from pytest_codspeed import BenchmarkFixture
from reflex_base.utils.format import json_dumps

from reflex.state import StateUpdate, serialize_state_update

from .support.events import PayloadKind, make_payload, wire_edge_cases


@pytest.mark.parametrize(
    ("kind", "rows"),
    [
        pytest.param(PayloadKind.SCALAR, 100, id="scalar_100b"),
        pytest.param(PayloadKind.SCALAR, 10_000, id="scalar_10kb"),
        pytest.param(PayloadKind.SCALAR, 1_000_000, id="scalar_1mb"),
        pytest.param(PayloadKind.MAPPING, 100, id="mapping_100"),
        pytest.param(PayloadKind.DATACLASS, 1000, id="dataclass_1000"),
        pytest.param(PayloadKind.MODEL, 1000, id="model_1000"),
    ],
)
def test_state_update_wire_serialization(
    kind: PayloadKind,
    rows: int,
    benchmark: BenchmarkFixture,
):
    """Benchmark encoding representative state updates to socket JSON.

    Args:
        kind: Payload shape.
        rows: Payload size parameter.
        benchmark: The CodSpeed benchmark fixture.
    """
    update = StateUpdate(
        delta={"performance_state": {"payload": make_payload(kind, rows)}}
    )
    encoded = benchmark(lambda: json_dumps(update))
    assert encoded


def test_state_update_dataclass_serialization(benchmark: BenchmarkFixture):
    """Benchmark conversion of a state update into its transport dictionary.

    Args:
        benchmark: The CodSpeed benchmark fixture.
    """
    update = StateUpdate(delta={"performance_state": {"payload": list(range(10_000))}})
    result = benchmark(lambda: serialize_state_update(update))
    assert result["delta"]


def test_wire_edge_case_serialization(benchmark: BenchmarkFixture):
    """Benchmark the complete set of supported special wire values.

    Args:
        benchmark: The CodSpeed benchmark fixture.
    """
    payload = wire_edge_cases()
    encoded = benchmark(lambda: json_dumps(payload))
    assert "Reflex" in encoded
