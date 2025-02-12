from pytest_codspeed import BenchmarkFixture

from reflex.compiler.compiler import _compile_page, _compile_stateful_components
from reflex.components.component import Component


def test_compile_page(evaluated_page: Component, benchmark: BenchmarkFixture):
    benchmark(lambda: _compile_page(evaluated_page, None))


def test_compile_stateful(evaluated_page: Component, benchmark: BenchmarkFixture):
    benchmark(lambda: _compile_stateful_components([evaluated_page]))


def test_get_all_imports(evaluated_page: Component, benchmark: BenchmarkFixture):
    benchmark(lambda: evaluated_page._get_all_imports())
