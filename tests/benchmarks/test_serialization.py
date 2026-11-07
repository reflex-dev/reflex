"""Benchmarks for state-update and wire serialization."""

from collections.abc import Callable
from typing import Any

import pytest
from pytest_codspeed import BenchmarkFixture
from reflex_base.utils.format import json_dumps

from reflex.state import StateUpdate, serialize_state_update

from .support.events import PayloadKind, make_payload, wire_edge_cases


def _new_update_per_round(
    payload: object,
) -> Callable[[], tuple[tuple[StateUpdate], dict[str, Any]]]:
    """Make a setup that hands each measured round a new update of the payload.

    An update encodes its fields once and keeps them, so a reused one would
    measure a cache hit after the first round.

    Args:
        payload: The value the update's delta holds.

    Returns:
        The CodSpeed pedantic setup.
    """

    def setup() -> tuple[tuple[StateUpdate], dict[str, Any]]:
        """Wrap the payload in a new update.

        Returns:
            CodSpeed pedantic positional and keyword arguments.
        """
        return ((StateUpdate(delta={"performance_state": {"payload": payload}}),), {})

    return setup


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
    encoded = benchmark.pedantic(
        json_dumps, setup=_new_update_per_round(make_payload(kind, rows))
    )
    assert encoded


def test_state_update_dataclass_serialization(benchmark: BenchmarkFixture):
    """Benchmark conversion of a state update into its transport dictionary.

    Args:
        benchmark: The CodSpeed benchmark fixture.
    """
    result = benchmark.pedantic(
        serialize_state_update, setup=_new_update_per_round(list(range(10_000)))
    )
    assert result["delta"]


def test_wire_edge_case_serialization(benchmark: BenchmarkFixture):
    """Benchmark the complete set of supported special wire values.

    Args:
        benchmark: The CodSpeed benchmark fixture.
    """
    payload = wire_edge_cases()
    encoded = benchmark(lambda: json_dumps(payload))
    assert "Reflex" in encoded
