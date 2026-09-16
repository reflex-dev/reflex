"""Benchmarks for ``reflex_base.utils.types._isinstance``.

``_isinstance`` validates state var assignments, computed var reads, and
component props. With ``nested=1`` container checks recurse per element,
so these cover the scalar fast path and large-container element paths.
"""

from typing import Any, TypedDict

import pytest
from pytest_codspeed import BenchmarkFixture
from reflex_base.utils.types import _isinstance

N = 10_000


class _Element(TypedDict):
    """Element for the typed-dict path."""

    x: int
    y: str


_INTS = list(range(N))
_DICTS = [{"a": 1, "b": 2} for _ in range(N)]
_OPTIONALS = [1, None] * (N // 2)
_ELEMENTS: list[_Element] = [{"x": 1, "y": "s"} for _ in range(N)]


@pytest.mark.parametrize(
    ("obj", "hint"),
    [
        pytest.param(_INTS, list[int], id="list_int"),
        pytest.param(_DICTS, list[dict[str, int]], id="list_dict"),
        pytest.param(_OPTIONALS, list[int | None], id="list_optional"),
        pytest.param(_ELEMENTS, list[_Element], id="list_typeddict"),
    ],
)
def test_isinstance_container(obj: list[Any], hint: type, benchmark: BenchmarkFixture):
    """Benchmark per-element validation of a large container var.

    Args:
        obj: The container to validate.
        hint: The declared var type.
        benchmark: The codspeed benchmark fixture.
    """
    benchmark(lambda: _isinstance(obj, hint, nested=1, treat_var_as_type=False))


def test_isinstance_scalar(benchmark: BenchmarkFixture):
    """Benchmark the scalar fast path.

    Args:
        benchmark: The codspeed benchmark fixture.
    """

    @benchmark
    def _():
        for i in _INTS:
            _isinstance(i, int, nested=1, treat_var_as_type=False)
