from collections.abc import Callable

from pytest_codspeed import BenchmarkFixture
from reflex_base.components.component import Component
from reflex_base.plugins import CompilerHooks

from reflex.compiler.plugins import DefaultPagePlugin

from .fixtures import BenchmarkPage


def test_evaluate_page(
    unevaluated_page: Callable[[], Component], benchmark: BenchmarkFixture
):
    benchmark(unevaluated_page)


def test_evaluate_page_single_pass(
    unevaluated_page: Callable[[], Component],
    benchmark: BenchmarkFixture,
):
    hooks = CompilerHooks(plugins=(DefaultPagePlugin(),))
    page = BenchmarkPage(route="/benchmark", component=unevaluated_page)
    benchmark(lambda: hooks.eval_page(page.component, page=page))
