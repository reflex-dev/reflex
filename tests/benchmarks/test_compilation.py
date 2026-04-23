from pytest_codspeed import BenchmarkFixture
from reflex_base.components.component import Component

from reflex.compiler.compiler import _compile_page, _compile_stateful_components


def import_templates():
    # Importing the templates module to avoid the import time in the benchmark
    import reflex.compiler.templates  # noqa: F401


def test_compile_page(evaluated_page: Component, benchmark: BenchmarkFixture):
    import_templates()

    benchmark(lambda: _compile_page(evaluated_page))


def test_compile_stateful(evaluated_page: Component, benchmark: BenchmarkFixture):
    import_templates()

    benchmark(lambda: _compile_stateful_components([evaluated_page]))


def test_get_all_imports(evaluated_page: Component, benchmark: BenchmarkFixture):
    benchmark(lambda: evaluated_page._get_all_imports())
