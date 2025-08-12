from collections.abc import Callable

from pytest_codspeed import BenchmarkFixture

from reflex.components.component import Component


def test_evaluate_page(
    unevaluated_page: Callable[[], Component], benchmark: BenchmarkFixture
):
    benchmark(unevaluated_page)
