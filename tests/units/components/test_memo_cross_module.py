"""Cross-module ``@rx.memo`` collision tests driven through the real pipeline.

These exercise the full define -> register -> compile_memo_components -> page
compile -> validate_imports chain across REAL fixture modules (see
``memo_fixtures/``), the integration point that isolated per-module unit tests
missed. Each test imports the fixtures fresh so import-time registration runs
again after ``preserve_memo_registries`` has snapshotted the global registry.
"""

import dataclasses
import importlib
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from reflex_base.components.component import Component
from reflex_base.components.memo import MEMOS
from reflex_base.plugins import CompileContext, CompilerHooks, PageContext
from reflex_base.utils import memo_paths

import reflex as rx
from reflex.compiler.plugins import default_page_plugins

_FIXTURE_PKG = "tests.units.components.memo_fixtures"


@pytest.fixture(autouse=True)
def _restore_memo_registries(preserve_memo_registries):
    """Snapshot and restore the global memo registry around each test."""


def _fresh_import(*short_names: str) -> tuple[Any, ...]:
    """Import fixture modules fresh so their memos re-register this test.

    ``preserve_memo_registries`` restores ``MEMOS`` between tests, but
    ``sys.modules`` keeps the fixture modules cached, so a plain ``import`` would
    be a silent no-op and the memos would be missing. Dropping the cached
    fixture modules first forces decoration to run again.

    Args:
        short_names: Fixture submodule names (e.g. ``"module_a"``).

    Returns:
        The freshly imported modules, in the requested order.
    """
    for key in [
        k for k in sys.modules if k == _FIXTURE_PKG or k.startswith(_FIXTURE_PKG + ".")
    ]:
        del sys.modules[key]
    return tuple(
        importlib.import_module(f"{_FIXTURE_PKG}.{name}") for name in short_names
    )


@dataclasses.dataclass(slots=True)
class _FakePage:
    route: str
    component: Callable[[], Component]
    title: Any = None
    description: Any = None
    image: str = ""
    meta: tuple[dict[str, Any], ...] = ()
    _source_module: str | None = None


def _compile_page(factory: Callable[[], Component]) -> PageContext:
    """Compile a single page through the production single-pass pipeline.

    Args:
        factory: Builds the page's component tree.

    Returns:
        The compiled page context (``.output_code`` holds the page JS).
    """
    ctx = CompileContext(
        pages=[_FakePage(route="/p", component=factory)],
        hooks=CompilerHooks(plugins=default_page_plugins()),
    )
    with ctx:
        ctx.compile()
    return ctx.compiled_pages["/p"]


def test_same_name_component_memos_in_different_modules_both_register():
    """Same-named component memos in two modules coexist without a collision."""
    module_a, module_b = _fresh_import("module_a", "module_b")

    sources = {
        d.source_module
        for d in MEMOS.values()
        if getattr(d, "export_name", None) == "MyWidget"
    }
    assert {module_a.__name__, module_b.__name__} <= sources


def test_page_using_two_same_name_component_memos_compiles():
    """A page using both same-named component memos imports each distinctly."""
    module_a, module_b = _fresh_import("module_a", "module_b")

    page = _compile_page(
        lambda: rx.fragment(
            module_a.my_widget(title="a"), module_b.my_widget(title="b")
        )
    )
    output = page.output_code or ""

    lib_a, sym_a = memo_paths.library_and_symbol(module_a.__name__, "MyWidget")
    lib_b, sym_b = memo_paths.library_and_symbol(module_b.__name__, "MyWidget")
    assert sym_a != sym_b
    assert f'import {{{sym_a}}} from "{lib_a}"' in output
    assert f'import {{{sym_b}}} from "{lib_b}"' in output


def test_cross_module_function_memos_same_name_compile():
    """Same-named function memos in two modules import under distinct symbols."""
    module_a, module_b = _fresh_import("module_a", "module_b")

    page = _compile_page(
        lambda: rx.fragment(
            rx.text(module_a.my_value(x=1)), rx.text(module_b.my_value(x=2))
        )
    )
    output = page.output_code or ""

    lib_a, sym_a = memo_paths.library_and_symbol(module_a.__name__, "my_value")
    lib_b, sym_b = memo_paths.library_and_symbol(module_b.__name__, "my_value")
    assert sym_a != sym_b
    assert f'import {{{sym_a}}} from "{lib_a}"' in output
    assert f'import {{{sym_b}}} from "{lib_b}"' in output


def test_memo_depends_on_memo_across_modules_in_grouped_file():
    """A grouped memo file imports a dependency's symbol and exports its own."""
    from reflex.compiler.compiler import compile_memo_components

    module_a, module_c = _fresh_import("module_a", "module_c")

    files, _ = compile_memo_components(tuple(MEMOS.values()))
    emitted = {Path(path).as_posix(): code for path, code in files}
    code_c = next(
        (
            code
            for path, code in emitted.items()
            if path.endswith("memo_fixtures/module_c.jsx")
        ),
        None,
    )
    assert code_c is not None, f"missing module_c memo file in {sorted(emitted)}"

    lib_a, sym_a = memo_paths.library_and_symbol(module_a.__name__, "MyWidget")
    _lib_c, sym_c = memo_paths.library_and_symbol(module_c.__name__, "MyWidget")
    _lib_consumer, sym_consumer = memo_paths.library_and_symbol(
        module_c.__name__, "Consumer"
    )

    # The dependency is imported from module_a's own file under module_a's
    # symbol; the local widget and consumer are emitted as local consts (the
    # group's own self-import is stripped), so the two never redeclare a symbol.
    assert sym_a != sym_c
    assert f'import {{{sym_a}}} from "{lib_a}"' in code_c
    assert f"export const {sym_consumer} = memo(" in code_c
    assert f"export const {sym_c} = memo(" in code_c


def test_three_modules_sharing_a_name_all_compile():
    """Three modules sharing a memo name all compile with distinct symbols."""
    module_a, module_b, module_c = _fresh_import("module_a", "module_b", "module_c")

    page = _compile_page(
        lambda: rx.fragment(
            module_a.my_widget(title="a"),
            module_b.my_widget(title="b"),
            module_c.my_widget(title="c"),
        )
    )
    output = page.output_code or ""

    symbols = []
    for module in (module_a, module_b, module_c):
        lib, sym = memo_paths.library_and_symbol(module.__name__, "MyWidget")
        assert f'import {{{sym}}} from "{lib}"' in output
        symbols.append(sym)
    assert len(set(symbols)) == 3


def test_hot_reload_reregistration_is_idempotent():
    """Reloading a module re-registers its memo in place, not as a duplicate."""
    (module_a,) = _fresh_import("module_a")
    importlib.reload(module_a)

    widgets = [
        d
        for d in MEMOS.values()
        if getattr(d, "export_name", None) == "MyWidget"
        and d.source_module == module_a.__name__
    ]
    assert len(widgets) == 1
