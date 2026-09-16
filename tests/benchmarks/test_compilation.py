import copy

from pytest_codspeed import BenchmarkFixture
from reflex_base.components.component import Component
from reflex_base.plugins import CompileContext, CompilerHooks, PageContext

from reflex.app import UnevaluatedPage
from reflex.compiler import compiler
from reflex.compiler.plugins import DefaultCollectorPlugin, default_page_plugins
from reflex.compiler.plugins.memoize import MemoizeStatefulPlugin

from .fixtures import ImportOnlyCollectorPlugin


def import_templates():
    # Importing the templates module to avoid the import time in the benchmark
    import reflex.compiler.templates  # noqa: F401


def _compile_page_context(component: Component) -> PageContext:
    # The compiler mutates the tree in place when it inserts memo wrappers, so
    # benchmark iterations need an isolated copy of the input.
    component = copy.deepcopy(component)
    page_ctx = PageContext(
        name="benchmark",
        route="/benchmark",
        root_component=component,
    )
    hooks = CompilerHooks(
        plugins=(MemoizeStatefulPlugin(), DefaultCollectorPlugin()),
    )
    compile_ctx = CompileContext(pages=[], hooks=hooks)

    with compile_ctx, page_ctx:
        page_ctx.root_component = hooks.compile_component(
            page_ctx.root_component,
            page_context=page_ctx,
            compile_context=compile_ctx,
        )
        hooks.compile_page(page_ctx, compile_context=compile_ctx)

    return page_ctx


def _collect_imports(component: Component) -> dict:
    """Collect only imports via a single walk of the component tree.

    Returns:
        The collapsed import dict for the page.
    """
    page_ctx = PageContext(
        name="benchmark",
        route="/benchmark",
        root_component=component,
    )
    hooks = CompilerHooks(plugins=(ImportOnlyCollectorPlugin(),))
    compile_ctx = CompileContext(pages=[], hooks=hooks)

    with compile_ctx, page_ctx:
        hooks.compile_component(
            component,
            page_context=page_ctx,
            compile_context=compile_ctx,
        )
        hooks.compile_page(page_ctx, compile_context=compile_ctx)

    return page_ctx.frontend_imports


def _compile_page(component: Component) -> str:
    page_ctx = _compile_page_context(component)
    page_ctx.frontend_imports = page_ctx.merged_imports(collapse=True)
    return compiler.compile_page_from_context(page_ctx)[1]


def _compile_page_full_context(unevaluated_page) -> str:
    page = UnevaluatedPage(route="/benchmark", component=unevaluated_page)
    compile_ctx = CompileContext(
        pages=[page],
        hooks=CompilerHooks(plugins=default_page_plugins()),
    )

    with compile_ctx:
        compiled_pages = compile_ctx.compile()

    output_code = compiled_pages["/benchmark"].output_code
    if output_code is None:
        msg = "CompileContext did not produce output code for the benchmark page."
        raise RuntimeError(msg)
    return output_code


def test_compile_page(
    evaluated_page: Component,
    benchmark: BenchmarkFixture,
):
    import_templates()

    benchmark(lambda: _compile_page(evaluated_page))


def test_compile_page_full_context(
    unevaluated_page,
    benchmark: BenchmarkFixture,
):
    import_templates()

    benchmark(lambda: _compile_page_full_context(unevaluated_page))


def test_get_all_imports(evaluated_page: Component, benchmark: BenchmarkFixture):
    benchmark(lambda: evaluated_page._get_all_imports())


def test_collect_imports(
    evaluated_page: Component,
    benchmark: BenchmarkFixture,
):
    benchmark(lambda: _collect_imports(evaluated_page))


def test_compile_all_artifacts(
    evaluated_page: Component,
    benchmark: BenchmarkFixture,
):
    """Compile a page collecting every artifact (imports, hooks, code, app_wrap).

    Exercises the full single walk of the component tree that produces imports,
    hooks, custom code, and app_wrap components together.
    """
    benchmark(
        lambda: _compile_page_context(evaluated_page).merged_imports(collapse=True)
    )
