"""Tests for the experimental disk-persisted incremental compile cache."""

import dataclasses
import json
from collections.abc import Callable, Sequence
from types import SimpleNamespace
from typing import Any, cast

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


def _compile(pages: Sequence[Any]) -> CompileContext:
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
        "epoch": "EPOCH",
        "all_imports": {},
        "pages": pages,
    }
    base.update(overrides)
    return base


def test_globals_match():
    m = _manifest({"/a": {}, "/b": {}})
    routes = {"/a", "/b"}
    assert disk_cache.globals_match(m, routes=routes, epoch="EPOCH")
    # a changed route set -> no match
    assert not disk_cache.globals_match(m, routes={"/a"}, epoch="EPOCH")
    # a changed global epoch -> no match
    assert not disk_cache.globals_match(m, routes=routes, epoch="OTHER")
    # a stale reflex version -> no match
    assert not disk_cache.globals_match(
        {**m, "reflex_version": "0.0.0-old"}, routes=routes, epoch="EPOCH"
    )


def test_partition_pages_detects_changed_source():
    pages = [
        _FakePage(route="/a", component=_page_a),
        _FakePage(route="/b", component=_page_b),
    ]
    # /a depends on x.py, /b depends on y.py (each at a recorded content hash).
    m = _manifest({
        "/a": {"dep_hashes": {"/proj/x.py": "h-x"}},
        "/b": {"dep_hashes": {"/proj/y.py": "h-y"}},
    })
    # The hasher reports /a's dep unchanged and /b's dep changed.
    current = {"/proj/x.py": "h-x", "/proj/y.py": "h-y-new"}
    miss = disk_cache.partition_pages(pages, m, lambda p: current.get(p))
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
    disk_cache.write_manifest(ctx, pages, ctx.all_imports, root=tmp_path)

    manifest = disk_cache.load_manifest()
    assert manifest is not None
    assert manifest["schema"] == disk_cache._SCHEMA
    assert set(manifest["pages"]) == {"/a", "/b", "/c"}
    for route in ("/a", "/b", "/c"):
        entry = manifest["pages"][route]
        # the manifest is pure bookkeeping: dep set + app-wrap keys + stateful flag
        assert set(entry) == {"dep_hashes", "app_wrap_keys", "is_stateful"}
        # these static pages register no new state
        assert entry["is_stateful"] is False
        # rendered output is never persisted (it already lives in .web, and is
        # never read back from the manifest) -> keeps the manifest small
        assert "output_code" not in entry
        assert "frontend_imports" not in entry
    # the app-wide merged imports round-trip cleanly
    restored = disk_cache._deserialize_imports(manifest["all_imports"])
    assert restored == ctx.all_imports


def test_unchanged_pages_compile_identically(tmp_path, monkeypatch):
    """The reuse correctness property: an unchanged page recompiles byte-for-byte.

    The disk cache leaves a hit page's already-on-disk ``.web`` file untouched, so
    reuse is correct if a fresh compile of that page yields identical output.
    Compile A, B, C; then compile A, B(edited), C; A and C must be byte-identical.
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

    app = rx.App()
    app.add_page(_page_a, route="/a")
    app.add_page(_page_c, route="/c")
    pages = list(app._unevaluated_pages.values())
    ctx = _compile(pages)
    disk_cache.write_manifest(ctx, pages, ctx.all_imports, root=tmp_path)
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

    app = rx.App()
    app.add_page(_page_a, route="/a")
    app.add_page(_page_c, route="/c")
    pages = list(app._unevaluated_pages.values())
    ctx = _compile(pages)
    disk_cache.write_manifest(ctx, pages, ctx.all_imports, root=tmp_path)
    _stub_externals(app, monkeypatch)

    # Simulate an edit to the first page: rewrite its manifest dependency set to
    # reference a file whose recorded hash no longer matches the current content,
    # so partitioning sees its dependency set as changed -> a miss (only it).
    edited_route = pages[0].route
    manifest_path = web / disk_cache._MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text())
    manifest["pages"][edited_route]["dep_hashes"] = {
        str(tmp_path / "view.py"): "stale-hash"
    }
    manifest_path.write_text(json.dumps(manifest))

    assert (
        disk_cache.try_incremental_rebuild(
            app, compiler_plugins=[], prerender_routes=False, root=tmp_path
        )
        is True
    )

    # The edited page was recompiled and written; its content matches a clean
    # compile of that page.
    output_path = ctx.compiled_pages[edited_route].output_path
    assert output_path is not None
    out_path = compiler_utils.resolve_path_of_web_dir(output_path)
    assert out_path.exists()
    assert (
        out_path.read_text(encoding="utf-8")
        == ctx.compiled_pages[edited_route].output_code
    )


def test_stateful_hit_is_marked_but_not_reevaluated(tmp_path, monkeypatch):
    """A stateful HIT page is recorded in the marker but never re-evaluated.

    The compile process only produces .web and exits; the serving backend
    re-evaluates the marked stateful pages itself, so re-evaluating them during
    the incremental rebuild was pure waste.
    """
    web = tmp_path / ".web"
    web.mkdir()
    monkeypatch.setattr(disk_cache.prerequisites, "get_web_dir", lambda: web)

    app = rx.App()
    app.add_page(_page_a, route="/a")
    pages = list(app._unevaluated_pages.values())
    route = pages[0].route
    ctx = _compile(pages)
    disk_cache.write_manifest(ctx, pages, ctx.all_imports, root=tmp_path)
    # Mark the page as a stateful HIT page in the manifest.
    manifest_path = web / disk_cache._MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text())
    manifest["pages"][route]["is_stateful"] = True
    manifest_path.write_text(json.dumps(manifest))
    _stub_externals(app, monkeypatch)

    reevaluated: list[str] = []
    monkeypatch.setattr(
        app, "_compile_page", lambda route, **k: reevaluated.append(route)
    )

    assert (
        disk_cache.try_incremental_rebuild(
            app, compiler_plugins=[], prerender_routes=False, root=tmp_path
        )
        is True
    )
    assert reevaluated == []
    assert route in app._stateful_pages


def test_load_manifest_rejects_wrong_schema(tmp_path, monkeypatch):
    web = tmp_path / ".web"
    web.mkdir()
    monkeypatch.setattr(disk_cache.prerequisites, "get_web_dir", lambda: web)
    (web / disk_cache._MANIFEST_FILE).write_text(json.dumps({"schema": 999}))
    assert disk_cache.load_manifest() is None


def test_update_manifest_for_misses_keeps_complete_imports(tmp_path, monkeypatch):
    web = tmp_path / ".web"
    web.mkdir()
    monkeypatch.setattr(disk_cache.prerequisites, "get_web_dir", lambda: web)
    monkeypatch.setattr(
        page_cache, "state_dependency_index", lambda root=None: ({}, set())
    )
    monkeypatch.setattr(page_cache, "page_dependency_hashes", lambda *a, **k: {})

    page = _FakePage(route="/a", component=_page_a)
    page_ctx = SimpleNamespace(app_wrap_components={}, frontend_imports={})
    miss_ctx = SimpleNamespace(compiled_pages={"/a": page_ctx}, stateful_routes=set())
    complete_imports = {"memo-lib": [ImportVar("MemoThing")]}
    manifest = _manifest({
        "/a": {"dep_hashes": {}, "app_wrap_keys": [], "is_stateful": False}
    })

    disk_cache._update_manifest_for_misses(
        manifest, cast(Any, miss_ctx), [page], complete_imports, root=tmp_path
    )

    written = json.loads((web / disk_cache._MANIFEST_FILE).read_text())
    assert disk_cache._deserialize_imports(written["all_imports"]) == complete_imports
