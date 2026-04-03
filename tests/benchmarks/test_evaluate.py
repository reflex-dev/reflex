from collections.abc import Callable

from pytest_codspeed import BenchmarkFixture
from reflex_core.components.component import Component

from .hotspots import evaluate_page_single_pass


def test_evaluate_page(
    unevaluated_page: Callable[[], Component], benchmark: BenchmarkFixture
):
    benchmark(unevaluated_page)


def test_evaluate_page_single_pass(
    unevaluated_page: Callable[[], Component],
    benchmark: BenchmarkFixture,
):
    benchmark(lambda: evaluate_page_single_pass(unevaluated_page))
