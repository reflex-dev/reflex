"""Benchmarks for generating string Var operations."""

import pytest
from pytest_codspeed import BenchmarkFixture
from reflex_base.vars.base import Var


@pytest.mark.parametrize("operation", ["length", "slice", "unit_slice"])
def test_string_operation_codegen(operation: str, benchmark: BenchmarkFixture) -> None:
    """Measure Python expression generation, excluding JavaScript execution.

    Args:
        operation: The string operation to generate.
        benchmark: The CodSpeed benchmark fixture.
    """
    value = Var(_js_expr="state.text").to(str)
    start = Var(_js_expr="state.start").to(int)
    stop = Var(_js_expr="state.stop").to(int)
    operations = {
        "length": value.length,
        "slice": lambda: value[start:stop],
        "unit_slice": lambda: value[start:stop:1],
    }
    benchmark(lambda: str(operations[operation]()))
