"""Benchmarks for literal construction and metadata dispatch."""

import pytest
from pytest_codspeed import BenchmarkFixture
from reflex_base.vars.base import LiteralVar


@pytest.mark.parametrize("metadata", [False, True])
def test_literal_row_dispatch(metadata: bool, benchmark: BenchmarkFixture) -> None:
    """Measure dispatch on a mixed builtin row with the normal registry.

    Args:
        metadata: Whether to collect metadata instead of constructing literals.
        benchmark: The CodSpeed benchmark fixture.
    """
    row = {"id": 1, "name": "Alice", "score": 0.5, "active": True}
    operation = (
        LiteralVar._get_all_var_data_without_creating_var_dispatch
        if metadata
        else LiteralVar.create
    )
    benchmark(lambda: tuple(operation(value) for value in row.values()))
