"""End-to-end test for ``CompilerSession.compile_app_ir`` covering D10/D11.

Builds a multi-page IR app plus theme, global state, and plugin manifest,
sends it all to the Rust compiler, and asserts the right output files come
back.
"""

from __future__ import annotations

import pytest

pytest.importorskip("reflex_compiler_rust._native")

from reflex.compiler.ir import builder as ir
from reflex.compiler.ir import schema  # noqa: F401  (sanity import)
from reflex.compiler.session import CompilerSession


@pytest.fixture(scope="module")
def session() -> CompilerSession:
    return CompilerSession()


def _theme_ir() -> list:
    return [
        schema.SCHEMA_VERSION,
        [["accentColor", "#ff0080"], ["radiusMd", "8px"]],
        "body { margin: 0; }",
        "light",
    ]


def _global_state_ir() -> list:
    return [
        schema.SCHEMA_VERSION,
        b"{\"count\": 0}",
        b"{}",
        [],
    ]


def _plugin_manifest_ir() -> list:
    return [
        schema.SCHEMA_VERSION,
        [
            ["radix", [], ["@radix-ui/themes/styles.css"]],
        ],
    ]


def test_compile_app_emits_all_artifacts(session: CompilerSession) -> None:
    pages = [
        ("Index", "/", ir.page(route="/", root=ir.text("home"))),
        ("About", "/about", ir.page(route="/about", root=ir.text("about"))),
        ("Docs", "/docs", ir.page(route="/docs", root=ir.text("docs"))),
    ]
    out = session.compile_app_ir(
        pages,
        theme=_theme_ir(),
        global_state=_global_state_ir(),
        plugin_manifest=_plugin_manifest_ir(),
    )
    files = out.files()  # type: ignore[attr-defined]
    paths = sorted(files.keys())

    # Per-page modules.
    assert "pages/index.jsx" in paths
    assert "pages/about.jsx" in paths
    assert "pages/docs.jsx" in paths

    # Theme CSS.
    assert "src/styles/theme.css" in paths
    assert b"--accent-color: #ff0080;" in files["src/styles/theme.css"]

    # Context shell.
    assert "src/context.js" in paths
    assert b"initialState = {\"count\": 0}" in files["src/context.js"]

    # AppWrap with the plugin stylesheet pulled in.
    assert "src/AppWrap.jsx" in paths
    assert b"@radix-ui/themes/styles.css" in files["src/AppWrap.jsx"]

    # Vite config.
    assert "vite.config.js" in paths
    assert b"defineConfig" in files["vite.config.js"]


def test_compile_app_parallel_caches_across_pages(session: CompilerSession) -> None:
    """rayon over pages must still hit the content-hash cache on repeat runs."""
    session.clear_cache()
    pages = [
        ("A", "/a", ir.page(route="/a", root=ir.text("aaa"))),
        ("B", "/b", ir.page(route="/b", root=ir.text("bbb"))),
        ("C", "/c", ir.page(route="/c", root=ir.text("ccc"))),
    ]
    _ = session.compile_app_ir(pages)
    assert session.cache_len() == 3

    # Compile again — every page is a cache hit.
    _ = session.compile_app_ir(pages)
    assert session.cache_len() == 3
