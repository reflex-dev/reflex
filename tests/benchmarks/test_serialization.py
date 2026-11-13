"""Benchmarks for state-update and wire serialization.

A single encode of a small payload takes a few microseconds, short enough for
the fixed cost of entering the measured call and the state of the CPU caches to
decide the result. Such payloads are encoded several times per measured call
so every benchmark here does a comparable amount of work.
"""

import pytest
from pytest_codspeed import BenchmarkFixture
from reflex_base.utils.format import json_dumps

from reflex.state import StateUpdate, serialize_state_update

from .support.events import PayloadKind, make_payload, wire_edge_cases

EDGE_CASE_ENCODES = 25
UPDATE_CONVERSIONS = 1000


@pytest.mark.parametrize(
    ("kind", "rows", "encodes"),
    [
        pytest.param(PayloadKind.SCALAR, 100, 100, id="scalar_100b"),
        pytest.param(PayloadKind.SCALAR, 10_000, 10, id="scalar_10kb"),
        pytest.param(PayloadKind.SCALAR, 1_000_000, 1, id="scalar_1mb"),
        pytest.param(PayloadKind.MAPPING, 100, 20, id="mapping_100"),
        pytest.param(PayloadKind.DATACLASS, 1000, 1, id="dataclass_1000"),
        pytest.param(PayloadKind.MODEL, 1000, 1, id="model_1000"),
    ],
)
def test_state_update_wire_serialization(
    kind: PayloadKind,
    rows: int,
    encodes: int,
    benchmark: BenchmarkFixture,
):
    """Benchmark encoding representative state updates to socket JSON.

    Args:
        kind: Payload shape.
        rows: Payload size parameter.
        encodes: Times the update is encoded per measured call.
        benchmark: The CodSpeed benchmark fixture.
    """
    update = StateUpdate(
        delta={"performance_state": {"payload": make_payload(kind, rows)}}
    )
    encoded = benchmark(lambda: [json_dumps(update) for _ in range(encodes)])
    assert encoded == [json_dumps(update)] * encodes


def test_state_update_dataclass_serialization(benchmark: BenchmarkFixture):
    """Benchmark conversion of a state update into its transport dictionary.

    Every update sent goes through this conversion. It takes well under a
    microsecond, so each measured call converts ``UPDATE_CONVERSIONS`` times.

    Args:
        benchmark: The CodSpeed benchmark fixture.
    """
    payload = list(range(10_000))
    update = StateUpdate(delta={"performance_state": {"payload": payload}})
    result = benchmark(
        lambda: [serialize_state_update(update) for _ in range(UPDATE_CONVERSIONS)]
    )
    assert result == [{"delta": {"performance_state": {"payload": payload}}}] * (
        UPDATE_CONVERSIONS
    )


def test_wire_edge_case_serialization(benchmark: BenchmarkFixture):
    """Benchmark the complete set of supported special wire values.

    Args:
        benchmark: The CodSpeed benchmark fixture.
    """
    payload = wire_edge_cases()
    encoded = benchmark(lambda: [json_dumps(payload) for _ in range(EDGE_CASE_ENCODES)])
    assert encoded == [json_dumps(payload)] * EDGE_CASE_ENCODES
