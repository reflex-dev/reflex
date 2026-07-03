"""Tests for the experimental disk-persisted incremental compile cache."""

import dataclasses
import json
from collections.abc import Callable, Sequence
from pathlib import Path
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


def _use_tmp_web_dir(tmp_path, monkeypatch):
    """Point every ``get_web_dir`` binding (module attr + env) at a tmp web dir.

    Args:
        tmp_path: The test's tmp directory.
        monkeypatch: The pytest monkeypatch fixture.

    Returns:
        The created web directory path.
    """
    web = tmp_path / ".web"
    web.mkdir()
    monkeypatch.setattr(disk_cache.prerequisites, "get_web_dir", lambda: web)
    monkeypatch.setenv("REFLEX_WEB_WORKDIR", str(web))
    return web


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
    _use_tmp_web_dir(tmp_path, monkeypatch)

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
        # the manifest is pure bookkeeping: dep set + app-wrap keys + flags
        assert set(entry) == {
            "dep_hashes",
            "app_wrap_keys",
            "is_stateful",
            "has_memos",
        }
        # these static pages register no new state and contribute no memos
        assert entry["is_stateful"] is False
        assert entry["has_memos"] is False
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
    _use_tmp_web_dir(tmp_path, monkeypatch)

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


_CONTEXTS_STUB = "// contexts stub"


def _stub_externals(app, monkeypatch):
    """Stub the side-effecting steps the fast path runs on a real app."""
    import reflex.utils.frontend_skeleton as fs
    from reflex.compiler import utils as compiler_utils

    monkeypatch.setattr(app, "_get_frontend_packages", lambda *a, **k: None)
    monkeypatch.setattr(app, "_add_optional_endpoints", lambda *a, **k: None)
    monkeypatch.setattr(app, "_validate_var_dependencies", lambda *a, **k: None)
    monkeypatch.setattr(app, "_write_stateful_pages_marker", lambda *a, **k: None)
    # Serializing the real root state tree would pick up unrelated state
    # classes from other collected test modules.
    monkeypatch.setattr(
        "reflex.compiler.compiler.compile_contexts",
        lambda state, theme: (compiler_utils.get_context_path(), _CONTEXTS_STUB),
    )
    monkeypatch.setattr(fs, "update_react_router_config", lambda **k: None)
    monkeypatch.setattr(fs, "update_entry_client", lambda *a, **k: None)


def test_incremental_rebuild_all_hits(tmp_path, monkeypatch):
    _use_tmp_web_dir(tmp_path, monkeypatch)

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

    web = _use_tmp_web_dir(tmp_path, monkeypatch)

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
    # The same-module hit page contributed no memos, so it is reused, not
    # recompiled (its output was never written to this fresh web dir).
    hit_output_path = ctx.compiled_pages[pages[1].route].output_path
    assert hit_output_path is not None
    assert not compiler_utils.resolve_path_of_web_dir(hit_output_path).exists()


def test_stateful_hit_is_marked_but_not_reevaluated(tmp_path, monkeypatch):
    """A stateful HIT page is recorded in the marker but never re-evaluated.

    The compile process only produces .web and exits; the serving backend
    re-evaluates the marked stateful pages itself, so re-evaluating them during
    the incremental rebuild was pure waste.
    """
    web = _use_tmp_web_dir(tmp_path, monkeypatch)

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


def test_incremental_rebuild_regenerates_contexts(tmp_path, monkeypatch):
    """State defaults/client-storage are baked into the contexts file and a
    state-module edit never bumps the epoch, so the incremental path must
    always re-emit it.
    """
    from reflex.compiler import utils as compiler_utils

    _use_tmp_web_dir(tmp_path, monkeypatch)

    app = rx.App()
    app.add_page(_page_a, route="/a")
    pages = list(app._unevaluated_pages.values())
    ctx = _compile(pages)
    disk_cache.write_manifest(ctx, pages, ctx.all_imports, root=tmp_path)
    _stub_externals(app, monkeypatch)

    assert (
        disk_cache.try_incremental_rebuild(
            app, compiler_plugins=[], prerender_routes=False, root=tmp_path
        )
        is True
    )

    out_path = compiler_utils.resolve_path_of_web_dir(compiler_utils.get_context_path())
    assert out_path.exists()
    assert out_path.read_text(encoding="utf-8") == _CONTEXTS_STUB


def test_incremental_rebuild_copies_assets(tmp_path, monkeypatch):
    """An assets-only edit is an all-hit rebuild, so the incremental path must
    run the same assets -> public copy as the full compile.
    """
    web = _use_tmp_web_dir(tmp_path, monkeypatch)
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "logo.svg").write_text("<svg/>")

    app = rx.App()
    app.add_page(_page_a, route="/a")
    pages = list(app._unevaluated_pages.values())
    ctx = _compile(pages)
    disk_cache.write_manifest(ctx, pages, ctx.all_imports, root=tmp_path)
    _stub_externals(app, monkeypatch)

    assert (
        disk_cache.try_incremental_rebuild(
            app, compiler_plugins=[], prerender_routes=False, root=tmp_path
        )
        is True
    )

    assert (web / "public" / "logo.svg").read_text() == "<svg/>"


@rx.memo
def _badge(text: str) -> Component:
    return rx.el.span(text, class_name="badge")


def _page_with_user_memo() -> Component:
    return rx.el.div(rx.el.h1("Memo page"), _badge(text="hello"))


def test_incremental_rebuild_rewrites_changed_user_memo(
    tmp_path, monkeypatch, preserve_memo_registries
):
    """Editing a user ``@rx.memo`` module must rewrite its mirrored memo file.

    The memo's module file is in the dep set of every page that imports it, so
    those pages miss — but only auto-memo contributions were being written,
    leaving the user memo's generated JS stale.
    """
    from reflex.compiler import compiler
    from reflex.compiler import utils as compiler_utils

    web = _use_tmp_web_dir(tmp_path, monkeypatch)

    app = rx.App()
    app.add_page(_page_with_user_memo, route="/memo")
    pages = list(app._unevaluated_pages.values())
    memo_route = pages[0].route
    ctx = _compile(pages)
    disk_cache.write_manifest(ctx, pages, ctx.all_imports, root=tmp_path)
    _stub_externals(app, monkeypatch)

    # Simulate an edit to this module (which defines the user memo): record a
    # stale hash for its file so the page importing the memo misses.
    module_file = str(Path(__file__).resolve())
    manifest_path = web / disk_cache._MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text())
    manifest["pages"][memo_route]["dep_hashes"] = {module_file: "stale-hash"}
    manifest_path.write_text(json.dumps(manifest))

    assert (
        disk_cache.try_incremental_rebuild(
            app, compiler_plugins=[], prerender_routes=False, root=tmp_path
        )
        is True
    )

    # The user memo's mirrored file was re-emitted with its export.
    from reflex_base.components.memo import MEMOS, MemoComponentDefinition

    badge_def = next(m for m in MEMOS.values() if m.source_module == __name__)
    assert isinstance(badge_def, MemoComponentDefinition)
    memo_files, _ = compiler.compile_memo_components([badge_def])
    assert memo_files
    for mpath, _mcode in memo_files:
        out_path = compiler_utils.resolve_path_of_web_dir(mpath)
        assert out_path.exists()
        assert badge_def.export_name in out_path.read_text(encoding="utf-8")


class _MemoCacheState(rx.State):
    value: str = "x"
    other: str = "y"


def _page_e() -> Component:
    return rx.el.div(rx.el.p(_MemoCacheState.value, class_name="e"), rx.el.h1("E"))


def _page_f() -> Component:
    return rx.el.div(rx.el.p(_MemoCacheState.other, class_name="f"), rx.el.h2("F"))


def test_incremental_miss_keeps_sibling_memo_exports(
    tmp_path, monkeypatch, preserve_memo_registries
):
    """A miss must not clobber memo exports owned by hit pages.

    Auto-memo output is grouped into one file per source module. Pages E and F
    live in this module and each contributes a stateful auto memo, so both land
    in the same mirrored file. When only E misses (e.g. a data-file edit),
    rewriting that file from E's contributions alone drops F's export while
    F's reused page module still imports it.
    """
    from reflex.compiler import compiler
    from reflex.compiler import utils as compiler_utils

    web = _use_tmp_web_dir(tmp_path, monkeypatch)

    app = rx.App()
    app.add_page(_page_e, route="/e")
    app.add_page(_page_f, route="/f")
    pages = list(app._unevaluated_pages.values())
    route_e, route_f = pages[0].route, pages[1].route
    ctx = _compile(pages)

    e_memos = list(ctx.compiled_pages[route_e].memo_contributions.values())
    f_memos = list(ctx.compiled_pages[route_f].memo_contributions.values())
    assert e_memos, "page E must contribute an auto memo"
    assert f_memos, "page F must contribute an auto memo"

    # Simulate the full compile's on-disk memo state (shared grouped file).
    memo_files, _ = compiler.compile_memo_components([*e_memos, *f_memos])
    assert memo_files
    for mpath, mcode in memo_files:
        compiler_utils.write_file(compiler_utils.resolve_path_of_web_dir(mpath), mcode)

    disk_cache.write_manifest(ctx, pages, ctx.all_imports, root=tmp_path)
    _stub_externals(app, monkeypatch)

    # Make only page E miss (a dependency of E changed, e.g. a data file).
    manifest_path = web / disk_cache._MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text())
    manifest["pages"][route_e]["dep_hashes"] = {str(tmp_path / "data.md"): "stale-hash"}
    manifest_path.write_text(json.dumps(manifest))

    assert (
        disk_cache.try_incremental_rebuild(
            app, compiler_plugins=[], prerender_routes=False, root=tmp_path
        )
        is True
    )

    # Every export (E's and F's) survives in the rewritten grouped file(s).
    for mpath, _mcode in memo_files:
        content = compiler_utils.resolve_path_of_web_dir(mpath).read_text(
            encoding="utf-8"
        )
        for memo_def in (*e_memos, *f_memos):
            assert memo_def.export_name in content


def test_load_manifest_rejects_wrong_schema(tmp_path, monkeypatch):
    web = _use_tmp_web_dir(tmp_path, monkeypatch)
    (web / disk_cache._MANIFEST_FILE).write_text(json.dumps({"schema": 999}))
    assert disk_cache.load_manifest() is None


def test_update_manifest_for_misses_keeps_complete_imports(tmp_path, monkeypatch):
    web = _use_tmp_web_dir(tmp_path, monkeypatch)
    monkeypatch.setattr(
        page_cache, "state_dependency_index", lambda root=None: ({}, set())
    )
    monkeypatch.setattr(page_cache, "page_dependency_hashes", lambda *a, **k: {})

    page = _FakePage(route="/a", component=_page_a)
    page_ctx = SimpleNamespace(
        app_wrap_components={}, frontend_imports={}, memo_contributions={}
    )
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
