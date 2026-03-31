from typing import Any

from pytest_codspeed import BenchmarkFixture
from reflex_core.components.component import Component

from reflex.compiler.compiler import _compile_page, _compile_stateful_components
from reflex.compiler.plugins import collect_component_tree_artifacts


def read_component_tree_multi_pass(component: Component) -> dict[str, Any]:
    """Read a component tree using the existing recursive collectors.

    Returns:
        The collected page artifacts.
    """
    return {
        "imports": component._get_all_imports(),
        "hooks": component._get_all_hooks(),
        "custom_code": component._get_all_custom_code(),
        "dynamic_imports": component._get_all_dynamic_imports(),
        "refs": component._get_all_refs(),
        "app_wrap_components": component._get_all_app_wrap_components(),
    }


def read_component_tree_single_pass(component: Component) -> dict[str, Any]:
    """Read a component tree once using the new single-pass collector.

    Returns:
        The collected page artifacts.
    """
    return collect_component_tree_artifacts(component)


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


def test_recursive_component_tree_reads_multi_pass(
    evaluated_page: Component,
    benchmark: BenchmarkFixture,
):
    benchmark(lambda: read_component_tree_multi_pass(evaluated_page))


def test_recursive_component_tree_reads_single_pass(
    evaluated_page: Component,
    benchmark: BenchmarkFixture,
):
    benchmark(lambda: read_component_tree_single_pass(evaluated_page))
