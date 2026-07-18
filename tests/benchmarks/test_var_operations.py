"""Benchmarks for Var construction and type dispatch."""

from pytest_codspeed import BenchmarkFixture

from reflex.vars import Var


def test_var_arithmetic_chain(benchmark: BenchmarkFixture):
    """Benchmark construction of a representative arithmetic expression.

    Args:
        benchmark: The CodSpeed benchmark fixture.
    """
    left = Var.create(1)
    right = Var.create(2)
    result = benchmark(lambda: ((left + right) * right - left) / right)
    assert result._js_expr


def test_var_to_dispatch(benchmark: BenchmarkFixture):
    """Benchmark conversion through the Var subclass registry.

    Args:
        benchmark: The CodSpeed benchmark fixture.
    """
    value = Var(_js_expr="value", _var_type=int)
    result = benchmark(lambda: value.to(float))
    assert result._var_type is float


def test_var_guess_type_dispatch(benchmark: BenchmarkFixture):
    """Benchmark inferred dispatch through the Var subclass registry.

    Args:
        benchmark: The CodSpeed benchmark fixture.
    """
    value = Var(_js_expr="value", _var_type=list[int])
    result = benchmark(value.guess_type)
    assert result._var_type == list[int]
