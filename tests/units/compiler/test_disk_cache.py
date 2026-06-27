"""Tests for the experimental disk-persisted incremental compile cache."""

import dataclasses
from collections.abc import Callable
from typing import Any

from reflex_base.components.component import Component
from reflex_base.plugins import CompileContext, CompilerHooks
from reflex_base.utils.imports import ImportVar

import reflex as rx
from reflex.compiler import disk_cache, page_cache
from reflex.compiler.plugins import default_page_plugins


@dataclasses.dataclass(slots=True)
class _FakePage:
    route: str
    component: Callable[[], Component]
    title: Any = None
    description: Any = None
    image: str = ""
    meta: tuple[dict[str, Any], ...] = ()
    _source_module: str | None = None


def _footer() -> Component:
    return rx.el.footer(rx.el.span("© Reflex"), class_name="footer")


def _page_a() -> Component:
    return rx.el.div(rx.el.h1("Page A"), _footer())


def _page_b() -> Component:
    return rx.el.div(rx.el.h1("Page B"), _footer())


def _page_b_edited() -> Component:
    return rx.el.div(rx.el.h1("Page B (edited)"), rx.el.p("new body"), _footer())


def _page_c() -> Component:
    return rx.el.div(rx.el.h1("Page C"), _footer())


def _compile(pages: list[_FakePage]) -> CompileContext:
    ctx = CompileContext(
        pages=pages,
        hooks=CompilerHooks(plugins=default_page_plugins()),
    )
    with ctx:
        ctx.compile()
    return ctx


def test_imports_round_trip():
    imports = {
        "react": [ImportVar("useEffect"), ImportVar("Fragment", is_default=False)],
        "@emotion/react": [ImportVar("jsx", alias="j", install=False)],
    }
    restored = disk_cache._deserialize_imports(disk_cache._serialize_imports(imports))
    assert restored == imports


def test_wrap_key_strs_is_sorted_and_stable():
    keys = [(200, "StrictMode"), (0, "AppWrap"), (45, "ColorMode")]
    assert disk_cache._wrap_key_strs(keys) == [
        "0:AppWrap",
        "200:StrictMode",
        "45:ColorMode",
    ]


def _manifest(pages: dict[str, dict], **overrides) -> dict:
    base = {
        "schema": disk_cache._SCHEMA,
        "reflex_version": page_cache._reflex_version(),
        "shared_fp": "SHARED",
        "state_hashes": {"/proj/state.py": "H"},
        "all_imports": {},
        "pages": pages,
    }
    base.update(overrides)
    return base


def test_globals_match():
    m = _manifest({"/a": {}, "/b": {}})
    routes = {"/a", "/b"}
    sh = {"/proj/state.py": "H"}
    assert disk_cache.globals_match(
        m, routes=routes, shared_fp="SHARED", state_hashes=sh
    )
    # a changed route set -> no match
    assert not disk_cache.globals_match(
        m, routes={"/a"}, shared_fp="SHARED", state_hashes=sh
    )
    # a changed shared fingerprint -> no match
    assert not disk_cache.globals_match(
        m, routes=routes, shared_fp="OTHER", state_hashes=sh
    )
    # a changed state hash -> no match (forces a full compile)
    assert not disk_cache.globals_match(
        m, routes=routes, shared_fp="SHARED", state_hashes={"/proj/state.py": "H2"}
    )
    # a stale reflex version -> no match
    assert not disk_cache.globals_match(
        {**m, "reflex_version": "0.0.0-old"},
        routes=routes,
        shared_fp="SHARED",
        state_hashes=sh,
    )


def test_partition_pages_detects_changed_source():
    pages = [
        _FakePage(route="/a", component=_page_a),
        _FakePage(route="/b", component=_page_b),
    ]
    fp_a = page_cache.page_source_fingerprint(_page_a)
    fp_b = page_cache.page_source_fingerprint(_page_b)
    # /a unchanged (stored fp matches), /b changed (stored fp differs)
    m = _manifest({
        "/a": {"page_source_fp": fp_a},
        "/b": {"page_source_fp": fp_b + "-stale"},
    })
    miss = disk_cache.partition_pages(pages, m)
    assert {p.route for p in miss} == {"/b"}


def test_write_and_load_manifest(tmp_path, monkeypatch):
    web = tmp_path / ".web"
    web.mkdir()
    monkeypatch.setattr(disk_cache.prerequisites, "get_web_dir", lambda: web)

    pages = [
        _FakePage(route="/a", component=_page_a),
        _FakePage(route="/b", component=_page_b),
        _FakePage(route="/c", component=_page_c),
    ]
    ctx = _compile(pages)
    disk_cache.write_manifest(ctx, pages, root=tmp_path)

    manifest = disk_cache.load_manifest()
    assert manifest is not None
    assert manifest["schema"] == disk_cache._SCHEMA
    assert set(manifest["pages"]) == {"/a", "/b", "/c"}
    # the cached output is exactly what the compile produced for each page
    for route in ("/a", "/b", "/c"):
        assert (
            manifest["pages"][route]["output_code"]
            == ctx.compiled_pages[route].output_code
        )
        # these static pages register no new state
        assert manifest["pages"][route]["is_stateful"] is False
    # imports round-trip cleanly
    restored = disk_cache._deserialize_imports(
        manifest["pages"]["/a"]["frontend_imports"]
    )
    assert restored == ctx.compiled_pages["/a"].frontend_imports


def test_unchanged_pages_compile_identically(tmp_path, monkeypatch):
    """The reuse correctness property: an unchanged page recompiles byte-for-byte.

    The disk cache reuses a hit page's stored ``output_code`` verbatim, so it is
    correct iff a fresh compile of that page yields identical output. Compile A,
    B, C; then compile A, B(edited), C; A and C must be byte-identical, and the
    manifest's cached A/C output must equal the fresh recompile.
    """
    web = tmp_path / ".web"
    web.mkdir()
    monkeypatch.setattr(disk_cache.prerequisites, "get_web_dir", lambda: web)

    pages = [
        _FakePage(route="/a", component=_page_a),
        _FakePage(route="/b", component=_page_b),
        _FakePage(route="/c", component=_page_c),
    ]
    ctx1 = _compile(pages)
    disk_cache.write_manifest(ctx1, pages, root=tmp_path)
    manifest = disk_cache.load_manifest()
    assert manifest is not None

    # "Edit" page B; recompile the whole app cleanly.
    pages_edited = [
        _FakePage(route="/a", component=_page_a),
        _FakePage(route="/b", component=_page_b_edited),
        _FakePage(route="/c", component=_page_c),
    ]
    ctx2 = _compile(pages_edited)

    # Unchanged pages are byte-identical across compiles -> safe to reuse.
    assert (
        ctx2.compiled_pages["/a"].output_code == ctx1.compiled_pages["/a"].output_code
    )
    assert (
        ctx2.compiled_pages["/c"].output_code == ctx1.compiled_pages["/c"].output_code
    )
    # B changed.
    assert (
        ctx2.compiled_pages["/b"].output_code != ctx1.compiled_pages["/b"].output_code
    )
    # The cached output we'd reuse for A/C equals a clean recompile of them.
    assert (
        manifest["pages"]["/a"]["output_code"] == ctx2.compiled_pages["/a"].output_code
    )
    assert (
        manifest["pages"]["/c"]["output_code"] == ctx2.compiled_pages["/c"].output_code
    )


def _stub_externals(app, monkeypatch):
    """Stub the side-effecting steps the fast path runs on a real app."""
    import reflex.utils.frontend_skeleton as fs

    monkeypatch.setattr(app, "_get_frontend_packages", lambda *a, **k: None)
    monkeypatch.setattr(app, "_add_optional_endpoints", lambda *a, **k: None)
    monkeypatch.setattr(app, "_validate_var_dependencies", lambda *a, **k: None)
    monkeypatch.setattr(app, "_write_stateful_pages_marker", lambda *a, **k: None)
    monkeypatch.setattr(fs, "update_react_router_config", lambda **k: None)
    monkeypatch.setattr(fs, "update_entry_client", lambda *a, **k: None)


def test_incremental_rebuild_all_hits(tmp_path, monkeypatch):
    web = tmp_path / ".web"
    web.mkdir()
    monkeypatch.setattr(disk_cache.prerequisites, "get_web_dir", lambda: web)
    monkeypatch.setattr(page_cache.prerequisites, "get_web_dir", lambda: web)

    app = rx.App()
    app.add_page(_page_a, route="/a")
    app.add_page(_page_c, route="/c")
    pages = list(app._unevaluated_pages.values())
    ctx = _compile(pages)
    disk_cache.write_manifest(ctx, pages, root=tmp_path)
    _stub_externals(app, monkeypatch)

    # Nothing changed -> every page is a hit -> fast path runs.
    assert (
        disk_cache.try_incremental_rebuild(
            app, compiler_plugins=[], prerender_routes=False, root=tmp_path
        )
        is True
    )


def test_incremental_rebuild_one_miss_writes_only_that_page(tmp_path, monkeypatch):
    from reflex.compiler import utils as compiler_utils

    web = tmp_path / ".web"
    web.mkdir()
    monkeypatch.setattr(disk_cache.prerequisites, "get_web_dir", lambda: web)
    monkeypatch.setattr(page_cache.prerequisites, "get_web_dir", lambda: web)

    app = rx.App()
    app.add_page(_page_a, route="/a")
    app.add_page(_page_c, route="/c")
    pages = list(app._unevaluated_pages.values())
    ctx = _compile(pages)
    disk_cache.write_manifest(ctx, pages, root=tmp_path)
    _stub_externals(app, monkeypatch)

    # Simulate an edit to the first page by making its source fingerprint differ
    # from what the manifest recorded (only for that page's component).
    edited = pages[0]
    real_fp = page_cache.page_source_fingerprint

    def fake_fp(component):
        if component is edited.component:
            return "edited-" + real_fp(component)
        return real_fp(component)

    monkeypatch.setattr(page_cache, "page_source_fingerprint", fake_fp)

    assert (
        disk_cache.try_incremental_rebuild(
            app, compiler_plugins=[], prerender_routes=False, root=tmp_path
        )
        is True
    )

    # The edited page was recompiled and written; its content matches a clean
    # compile of that page.
    out_path = compiler_utils.resolve_path_of_web_dir(
        ctx.compiled_pages[edited.route].output_path
    )
    assert out_path.exists()
    assert (
        out_path.read_text(encoding="utf-8")
        == ctx.compiled_pages[edited.route].output_code
    )


def test_load_manifest_rejects_wrong_schema(tmp_path, monkeypatch):
    import json

    web = tmp_path / ".web"
    web.mkdir()
    monkeypatch.setattr(disk_cache.prerequisites, "get_web_dir", lambda: web)
    (web / disk_cache._MANIFEST_FILE).write_text(json.dumps({"schema": 999}))
    assert disk_cache.load_manifest() is None
