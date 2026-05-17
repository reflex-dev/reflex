"""Tests for the run-rust pipeline.

The tests here cover the public surface in
:mod:`reflex.compiler.rust_pipeline`:

* :func:`scaffold_exists` — discriminates a ready ``.web/`` from an empty
  one.
* :func:`compile_pages` — emits JSX for every registered page directly
  through the Rust pipeline.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("reflex_base")
pytest.importorskip("reflex_components_core")
pytest.importorskip("reflex_compiler_rust._native")


import reflex as rx
from reflex.compiler import rust_pipeline
from reflex.compiler.session import CompilerSession


@pytest.fixture(scope="module")
def session() -> CompilerSession:
    return CompilerSession()


def test_scaffold_exists_true_when_all_present(tmp_path: Path) -> None:
    web = tmp_path / ".web"
    web.mkdir()
    (web / "package.json").write_text("{}")
    (web / "vite.config.js").write_text("// vite")
    (web / "reflex.json").write_text("{}")
    (web / "app").mkdir()
    (web / "utils").mkdir()

    assert rust_pipeline.scaffold_exists(web)


def test_scaffold_exists_false_when_file_missing(tmp_path: Path) -> None:
    web = tmp_path / ".web"
    web.mkdir()
    (web / "package.json").write_text("{}")
    (web / "vite.config.js").write_text("// vite")
    # reflex.json missing
    (web / "app").mkdir()
    (web / "utils").mkdir()

    assert not rust_pipeline.scaffold_exists(web)


def test_scaffold_exists_false_when_dir_missing(tmp_path: Path) -> None:
    web = tmp_path / ".web"
    web.mkdir()
    (web / "package.json").write_text("{}")
    (web / "vite.config.js").write_text("// vite")
    (web / "reflex.json").write_text("{}")
    # utils dir missing
    (web / "app").mkdir()

    assert not rust_pipeline.scaffold_exists(web)


def test_scaffold_exists_false_when_no_web(tmp_path: Path) -> None:
    assert not rust_pipeline.scaffold_exists(tmp_path / ".web")


def test_compile_pages_emits_pages(
    tmp_path: Path,
    session: CompilerSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``compile_pages`` emits one JSX file per registered page, never touching App._compile."""
    from reflex.utils import prerequisites

    web = tmp_path / ".web"
    web.mkdir()
    monkeypatch.setattr(prerequisites, "get_web_dir", lambda: web)

    app = rx.App()

    def index() -> rx.Component:
        return rx.box("hello rust")

    def about() -> rx.Component:
        return rx.text("about page")

    app.add_page(index, route="/")
    app.add_page(about, route="/about")

    # Sanity: App._pages must be empty — the Rust pipeline reads unevaluated only.
    assert not getattr(app, "_pages", {})

    written, all_imports = rust_pipeline.compile_pages(app, session=session)

    # ``add_page`` normalizes routes via ``format.format_route`` (strips
    # leading "/", maps "/" → "index"), so the output mirrors what the
    # registry stores. Plus the pipeline auto-adds the 404 slug if the
    # app didn't register one (matching ``App._compile``'s behaviour), so
    # the resulting set is the user's pages plus ``Page404.SLUG``.
    assert set(written.keys()) >= {"index", "about"}
    assert len(written) == 3
    for path in written.values():
        assert path.exists()
        contents = path.read_text()
        assert "jsx(" in contents
        assert "Component" in contents  # default export name

    # Body content survived through the Rust emit.
    all_text = "\n".join(p.read_text() for p in written.values())
    assert "hello rust" in all_text
    assert "about page" in all_text

    # Imports from at least one page should have been harvested for the
    # later ``bun install`` step.
    assert isinstance(all_imports, dict)

    # The Rust pipeline did NOT populate ``_pages`` (no legacy compile ran).
    assert not getattr(app, "_pages", {})


def test_compile_pages_routes_filter(
    tmp_path: Path,
    session: CompilerSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from reflex.utils import prerequisites

    web = tmp_path / ".web"
    web.mkdir()
    monkeypatch.setattr(prerequisites, "get_web_dir", lambda: web)

    app = rx.App()
    app.add_page(lambda: rx.text("a"), route="/a")
    app.add_page(lambda: rx.text("b"), route="/b")

    # Routes get normalized to "a", "b" inside ``add_page``; pass the
    # normalized form to ``routes=`` since that's what the pipeline keys on.
    written, _ = rust_pipeline.compile_pages(app, session=session, routes=["a"])
    assert set(written.keys()) == {"a"}


def _normalize_imports(d: dict) -> dict[str, list]:
    """Drop the ``defaultdict`` wrapping + sort entries by ``str()``.

    The order in which ``_get_all_imports`` and the Rust walker emit
    items can differ (HashMap vs ordered Python dict), so parity needs a
    canonical form. ``ImportVar`` is hashable but its repr is the most
    portable thing to sort by.

    Args:
        d: A ``ParsedImportDict``-shaped mapping.

    Returns:
        A plain ``dict`` with each library's items sorted by ``str()``.
    """
    return {lib: sorted(items, key=str) for lib, items in d.items()}


def _sample_component() -> rx.Component:
    """A tree that exercises every surface ``_get_all_imports`` walks.

    Returns:
        A Component covering library/tag imports, event-trigger imports,
        nested children, and the ``_get_components_in_props`` recursion
        (via ``rx.cond`` carrying Components in its props).
    """
    state_var = rx.Var(_js_expr="someState", _var_type=str)
    return rx.box(
        rx.text("hello"),
        rx.heading("title"),
        rx.cond(
            state_var,
            rx.button("click", on_click=lambda: rx.console_log("c")),
            rx.text("fallback"),
        ),
    )


def test_collect_all_imports_matches_python(session: CompilerSession) -> None:
    """The Rust ``collect_all_imports`` mirrors Python ``_get_all_imports``."""
    component = _sample_component()
    py_imports = component._get_all_imports()
    rust_imports = session.collect_all_imports(component)

    assert _normalize_imports(dict(rust_imports)) == _normalize_imports(
        dict(py_imports)
    )


def test_collect_all_imports_into_matches_python_merge_imports(
    session: CompilerSession,
) -> None:
    """``collect_all_imports_into`` matches ``merge_imports(target, _get_all_imports())``.

    The in-place variant applies the same ``$/utils/...`` prefix
    transform that the Python ``merge_imports`` wrapper does, so the
    final dict must match what the legacy two-step
    ``merge_imports(target, component._get_all_imports())`` would
    produce.
    """
    from reflex.compiler import utils as compiler_utils

    component = _sample_component()

    py_target: dict[str, list] = {}
    py_target = compiler_utils.merge_imports(py_target, component._get_all_imports())

    rust_target: dict[str, list] = {}
    session.collect_all_imports_into(rust_target, component)

    assert _normalize_imports(dict(rust_target)) == _normalize_imports(dict(py_target))


def test_merge_imports_into_applies_alias_prefix(session: CompilerSession) -> None:
    """``merge_imports_into`` rewrites ``/utils/...`` -> ``$/utils/...``."""
    from reflex_base.utils.imports import ImportVar

    target: dict[str, list] = {"react": [ImportVar(tag="useState")]}
    source = {
        "/utils/state": [ImportVar(tag="StateContexts")],
        "react": [ImportVar(tag="useEffect")],
    }
    session.merge_imports_into(target, source)

    assert "$/utils/state" in target
    assert "/utils/state" not in target
    assert len(target["react"]) == 2
