"""Benchmarks for inference from container values."""

import pytest
from pytest_codspeed import BenchmarkFixture
from reflex_base.vars.base import figure_out_type


@pytest.mark.parametrize("size", [100, 10_000, 100_000])
def test_mapping_type_inference(benchmark: BenchmarkFixture, size: int):
    """Infer a mapping's type without work proportional to its size.

    Args:
        benchmark: The benchmark fixture.
        size: The number of entries in the mapping.
    """
    value = {str(index): index for index in range(size)}
    benchmark(figure_out_type, value)
