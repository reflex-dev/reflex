from pytest_codspeed import BenchmarkFixture
from reflex_core.components.component import Component

from reflex.compiler.compiler import _compile_page, _compile_stateful_components

from .hotspots import (
    compile_page_full_context,
    compile_page_single_pass,
    get_all_imports_single_pass,
)


def import_templates():
    # Importing the templates module to avoid the import time in the benchmark
    import reflex.compiler.templates  # noqa: F401


def test_compile_page(evaluated_page: Component, benchmark: BenchmarkFixture):
    import_templates()

    benchmark(lambda: _compile_page(evaluated_page))


def test_compile_page_single_pass(
    evaluated_page: Component,
    benchmark: BenchmarkFixture,
):
    import_templates()

    benchmark(lambda: compile_page_single_pass(evaluated_page))


def test_compile_page_full_context(
    unevaluated_page,
    benchmark: BenchmarkFixture,
):
    import_templates()

    benchmark(lambda: compile_page_full_context(unevaluated_page))


def test_compile_stateful(evaluated_page: Component, benchmark: BenchmarkFixture):
    import_templates()

    benchmark(lambda: _compile_stateful_components([evaluated_page]))


def test_get_all_imports(evaluated_page: Component, benchmark: BenchmarkFixture):
    benchmark(lambda: evaluated_page._get_all_imports())


def test_get_all_imports_single_pass(
    evaluated_page: Component,
    benchmark: BenchmarkFixture,
):
    benchmark(lambda: get_all_imports_single_pass(evaluated_page))
