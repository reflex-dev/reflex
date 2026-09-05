"""Tests for the experimental disk-persisted incremental compile cache."""

import dataclasses
import hashlib
import itertools
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


def _compile(pages: Sequence[Any], app: Any = None) -> CompileContext:
    ctx = CompileContext(
        app=app,
        pages=pages,
        hooks=CompilerHooks(plugins=default_page_plugins()),
    )
    with ctx:
        ctx.compile()
    return ctx


def _unregister_state(cls: type[rx.State]) -> None:
    """Drop a state class from the registries, like the daemon registry reset.

    Lets a page evaluation re-define the same-named class in this process,
    mirroring what happens in the fork child between hot reloads.

    Args:
        cls: The state class to unregister.
    """
    from reflex_base.registry import RegistrationContext

    from reflex.state import all_base_state_classes

    ctx = RegistrationContext.ensure_context()
    full_name = cls.get_full_name()
    ctx.base_states.pop(full_name, None)
    parent = cls.get_parent_state()
    if parent is not None:
        ctx.base_state_substates.get(parent.get_full_name(), set()).discard(cls)
    all_base_state_classes.pop(full_name, None)


def test_imports_round_trip():
    imports = {
        "react": [ImportVar("useEffect"), ImportVar("Fragment", is_default=False)],
        "@emotion/react": [ImportVar("jsx", alias="j", install=False)],
    }
    restored = disk_cache._deserialize_imports(disk_cache._serialize_imports(imports))
    assert restored == imports


def test_serialize_imports_collapses_duplicates():
    """The manifest only needs the unique import set, in first-seen order.

    A full docs-app compile accumulates ~107k entries of which ~6k are unique;
    storing duplicates bloats the manifest and every later merge over it.
    """
    use_effect = ImportVar("useEffect")
    fragment = ImportVar("Fragment", is_default=False)
    imports = {
        "react": [use_effect, fragment, use_effect, use_effect, fragment],
        "@emotion/react": [ImportVar("jsx"), ImportVar("jsx")],
    }
    restored = disk_cache._deserialize_imports(disk_cache._serialize_imports(imports))
    assert restored == {
        "react": [use_effect, fragment],
        "@emotion/react": [ImportVar("jsx")],
    }


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
        "epoch_inputs": {},
        "all_imports": {},
        "pages": pages,
    }
    base.update(overrides)
    return base


def test_globals_mismatch_names_the_changed_input(tmp_path):
    m = _manifest({"/a": {}, "/b": {}}, epoch_inputs={"rxconfig.py": "<absent>"})
    routes = {"/a", "/b"}
    assert disk_cache.globals_mismatch(m, routes=routes, root=tmp_path) is None
    # a changed route set -> named added/removed routes
    reason = disk_cache.globals_mismatch(m, routes={"/a", "/c"}, root=tmp_path)
    assert reason is not None
    assert "/c" in reason
    assert "/b" in reason
    # a stale reflex version -> named versions
    reason = disk_cache.globals_mismatch(
        {**m, "reflex_version": "0.0.0-old"}, routes=routes, root=tmp_path
    )
    assert reason is not None
    assert "0.0.0-old" in reason


def test_globals_mismatch_validates_stored_inputs_only(tmp_path):
    """Epoch validation re-hashes the *stored* input set, never a recomputed one.

    ``app_dependency_files`` depends on what the current process happened to
    read/import during app import, which differs between a cold compile and a
    warm forked reload (non-purged module caches skip re-reads). Comparing a
    recomputed set against the stored one therefore mismatched on every hot
    reload; only stored inputs whose *content* changed may invalidate.
    """
    theme = tmp_path / "theme_config.py"
    theme.write_text("PRIMARY = 'red'")
    stored = {
        "reflex": page_cache._reflex_version(),
        # global files absent from this root at write time and still absent
        "rxconfig.py": "<absent>",
        f"app:{theme}": hashlib.sha256(theme.read_bytes()).hexdigest(),
    }
    m = _manifest({"/a": {}}, epoch_inputs=stored)
    # nothing on disk changed -> match, regardless of what a re-recorded
    # app-import read set would look like in this process
    assert disk_cache.globals_mismatch(m, routes={"/a"}, root=tmp_path) is None
    # a stored input's content changed -> mismatch naming that file
    theme.write_text("PRIMARY = 'blue'")
    reason = disk_cache.globals_mismatch(m, routes={"/a"}, root=tmp_path)
    assert reason is not None
    assert "theme_config.py" in reason
    # a stored global file appearing counts as a change too
    theme.write_text("PRIMARY = 'red'")
    (tmp_path / "rxconfig.py").write_text("import reflex")
    reason = disk_cache.globals_mismatch(m, routes={"/a"}, root=tmp_path)
    assert reason is not None
    assert "rxconfig.py" in reason


def test_format_path_list_relativizes_and_truncates():
    root = Path("/proj")
    assert disk_cache.format_path_list({"/proj/a.py", "other"}, root) == "a.py, other"
    many = {f"/proj/{i}.py" for i in range(8)}
    out = disk_cache.format_path_list(many, root, limit=3)
    assert out == "0.py, 1.py, 2.py (+5 more)"


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
            "state_fingerprint",
            "has_memos",
        }
        # these static pages register no new state and contribute no memos
        assert entry["is_stateful"] is False
        assert entry["state_fingerprint"] is None
        assert entry["has_memos"] is False
        # rendered output is never persisted (it already lives in .web, and is
        # never read back from the manifest) -> keeps the manifest small
        assert "output_code" not in entry
        assert "frontend_imports" not in entry
    # the app-wide merged imports round-trip cleanly (duplicates collapsed)
    restored = disk_cache._deserialize_imports(manifest["all_imports"])
    assert restored == {
        lib: list(dict.fromkeys(ivs)) for lib, ivs in ctx.all_imports.items()
    }


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


_TEST_STATE_MODULES = (__name__, "fp_mod_x")


def _scoped_contexts_snapshot(app) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """A ``_contexts_snapshot`` limited to the states this test file defines.

    Same shape and serialization as the real snapshot, but each test state is
    compiled standalone instead of walking the whole root state tree, which
    would pick up unrelated (and sometimes broken) state classes collected
    from other test modules.

    Args:
        app: The app being compiled.

    Returns:
        The (initial state, client storage) mappings for this file's states,
        or None when the app has no state tree.
    """
    if app is None or app._state is None:
        return None
    from reflex_base.registry import RegistrationContext

    from reflex.compiler import utils as compiler_utils

    initial: dict[str, Any] = {}
    storage: dict[str, dict[str, Any]] = {}
    ctx = RegistrationContext.ensure_context()
    for cls in list(ctx.base_states.values()):
        if cls.__module__ in _TEST_STATE_MODULES:
            initial.update(compiler_utils.compile_state(cls))
            for kind, entries in compiler_utils.compile_client_storage(cls).items():
                storage.setdefault(kind, {}).update(entries)
    return initial, storage


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
    monkeypatch.setattr(disk_cache, "_contexts_snapshot", _scoped_contexts_snapshot)
    monkeypatch.setattr(fs, "update_react_router_config", lambda **k: None)
    monkeypatch.setattr(fs, "update_entry_client", lambda *a, **k: None)
    monkeypatch.setattr(fs, "initialize_vite_config", lambda: None)


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


def test_incremental_rebuild_preserves_contexts_without_stateful_miss(
    tmp_path, monkeypatch
):
    """The contexts file is reused unless a stateful page missed.

    The full compile's contexts file holds every state's defaults, including
    states only registered while their page evaluates (exec'd demos, dynamic
    imports). An incremental process that evaluated no stateful pages has an
    incomplete registry; rewriting contexts from it drops those states and the
    frontend's dispatch map with them (``dispatch is not a function``). With no
    stateful miss, no state changed -> the on-disk file must stay untouched.
    """
    from reflex.compiler import utils as compiler_utils

    _use_tmp_web_dir(tmp_path, monkeypatch)

    app = rx.App()
    app.add_page(_page_a, route="/a")
    pages = list(app._unevaluated_pages.values())
    ctx = _compile(pages)
    disk_cache.write_manifest(ctx, pages, ctx.all_imports, root=tmp_path)
    _stub_externals(app, monkeypatch)

    full_contexts = "// complete contexts from the full compile"
    out_path = compiler_utils.resolve_path_of_web_dir(compiler_utils.get_context_path())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(full_contexts, encoding="utf-8")

    assert (
        disk_cache.try_incremental_rebuild(
            app, compiler_plugins=[], prerender_routes=False, root=tmp_path
        )
        is True
    )
    assert out_path.read_text(encoding="utf-8") == full_contexts


_state_counter = itertools.count()


def _page_s() -> Component:
    """A page that defines its state during evaluation (like exec'd docs demos).

    Each evaluation defines a fresh uniquely-named state class, so the page is
    marked stateful and repeated evaluations in one test process don't collide.

    Returns:
        The page component.
    """
    name = f"_ContextsState{next(_state_counter)}"
    state_cls: Any = type(
        name,
        (rx.State,),
        {"__annotations__": {"value": str}, "value": "", "__module__": __name__},
    )
    return rx.el.div(rx.el.p(state_cls.value), _footer())


def test_stateful_miss_evaluates_stateful_hits_then_rewrites_contexts(
    tmp_path, monkeypatch
):
    """A stateful miss forces a contexts rewrite from a *complete* registry.

    The stateful hit pages must be evaluated first (registering their
    evaluation-time states) so the rewritten contexts file keeps every state.
    """
    from reflex.compiler import utils as compiler_utils

    web = _use_tmp_web_dir(tmp_path, monkeypatch)

    app = rx.App()
    app.add_page(_page_s, route="/s")
    app.add_page(_page_c, route="/c")
    pages = list(app._unevaluated_pages.values())
    stateful_route, hit_route = pages[0].route, pages[1].route
    ctx = _compile(pages)
    assert stateful_route in ctx.stateful_routes
    disk_cache.write_manifest(ctx, pages, ctx.all_imports, root=tmp_path)
    _stub_externals(app, monkeypatch)

    # Make the stateful page a miss, and mark the hit page stateful so the
    # rebuild must re-register its states before compiling contexts.
    manifest_path = web / disk_cache._MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text())
    manifest["pages"][stateful_route]["dep_hashes"] = {
        str(tmp_path / "view.py"): "stale-hash"
    }
    manifest["pages"][hit_route]["is_stateful"] = True
    manifest_path.write_text(json.dumps(manifest))

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
    # Only the stateful HIT page is re-evaluated (the miss was compiled in the
    # miss context); then contexts are rewritten from the complete registry.
    assert reevaluated == [hit_route]
    out_path = compiler_utils.resolve_path_of_web_dir(compiler_utils.get_context_path())
    assert out_path.read_text(encoding="utf-8") == _CONTEXTS_STUB


def test_contexts_fingerprint_sensitivity():
    initial = {"root.s_one": {"value": ""}, "root.s_two": {"count": 0}}
    storage = {
        "cookies": {"root.s_one.token_rx_field_": {"name": "t"}},
        "local_storage": {},
        "session_storage": {},
    }
    base = disk_cache._contexts_fingerprint(["root.s_one"], initial, storage)
    # Stable across equal inputs and insensitive to name order.
    assert disk_cache._contexts_fingerprint(["root.s_one"], dict(initial), storage) == (
        base
    )
    both = disk_cache._contexts_fingerprint(
        ["root.s_one", "root.s_two"], initial, storage
    )
    assert (
        disk_cache._contexts_fingerprint(["root.s_two", "root.s_one"], initial, storage)
        == both
    )
    # Sensitive to which states, their initial values, and their client storage.
    assert disk_cache._contexts_fingerprint(["root.s_two"], initial, storage) != base
    assert (
        disk_cache._contexts_fingerprint(
            ["root.s_one"], {"root.s_one": {"value": "x"}}, storage
        )
        != base
    )
    assert (
        disk_cache._contexts_fingerprint(
            ["root.s_one"],
            initial,
            {"cookies": {}, "local_storage": {}, "session_storage": {}},
        )
        != base
    )


_FP_HOLDER: dict[str, Any] = {}


def _page_fp() -> Component:
    """A stateful page that defines the SAME state class on every evaluation.

    Mirrors a docs page whose exec'd demo code is unchanged between reloads.
    The previous definition must be unregistered before re-evaluation (the
    daemon's registry reset does this between hot reloads).

    Returns:
        The page component.
    """
    state_cls: Any = type(
        "_FixedFpState",
        (rx.State,),
        {"__annotations__": {"value": str}, "value": "", "__module__": "fp_mod_x"},
    )
    _FP_HOLDER["cls"] = state_cls
    return rx.el.div(rx.el.p(state_cls.value), _footer())


def test_stateful_miss_with_unchanged_states_reuses_contexts(tmp_path, monkeypatch):
    """A stateful miss whose states are unchanged must not rebuild contexts.

    Most content edits leave the page's evaluation-time states identical, so
    re-evaluating every stateful hit page just to rewrite an identical contexts
    file would waste nearly the whole hot reload.
    """
    from reflex.compiler import utils as compiler_utils

    web = _use_tmp_web_dir(tmp_path, monkeypatch)

    app = rx.App()
    app.add_page(_page_fp, route="/s")
    app.add_page(_page_c, route="/c")
    pages = list(app._unevaluated_pages.values())
    stateful_route, hit_route = pages[0].route, pages[1].route
    ctx = _compile(pages, app=app)
    assert stateful_route in ctx.stateful_routes
    # Stub before write_manifest: it fingerprints via the contexts snapshot.
    _stub_externals(app, monkeypatch)
    disk_cache.write_manifest(ctx, pages, ctx.all_imports, root=tmp_path)

    manifest_path = web / disk_cache._MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text())
    stored_fp = manifest["pages"][stateful_route]["state_fingerprint"]
    assert stored_fp  # the compile recorded the page's state config
    # Make the stateful page a miss; mark the hit page stateful so a contexts
    # rebuild (if wrongly triggered) would have to re-evaluate it.
    manifest["pages"][stateful_route]["dep_hashes"] = {
        str(tmp_path / "view.py"): "stale-hash"
    }
    manifest["pages"][hit_route]["is_stateful"] = True
    manifest_path.write_text(json.dumps(manifest))

    # The daemon child resets the registry before recompiling; drop the class
    # so the page's re-evaluation re-defines it identically.
    _unregister_state(_FP_HOLDER.pop("cls"))

    reevaluated: list[str] = []
    monkeypatch.setattr(
        app, "_compile_page", lambda route, **k: reevaluated.append(route)
    )
    sentinel = "// pre-existing contexts"
    out_path = compiler_utils.resolve_path_of_web_dir(compiler_utils.get_context_path())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(sentinel, encoding="utf-8")

    assert (
        disk_cache.try_incremental_rebuild(
            app, compiler_plugins=[], prerender_routes=False, root=tmp_path
        )
        is True
    )
    # Unchanged state config: no hit re-evaluation, contexts file untouched.
    assert reevaluated == []
    assert out_path.read_text(encoding="utf-8") == sentinel
    # The refreshed manifest records the same fingerprint for the miss page.
    refreshed = json.loads(manifest_path.read_text())
    assert refreshed["pages"][stateful_route]["state_fingerprint"] == stored_fp
    _unregister_state(_FP_HOLDER.pop("cls"))


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
    miss_ctx = SimpleNamespace(compiled_pages={"/a": page_ctx}, stateful_routes={})
    complete_imports = {"memo-lib": [ImportVar("MemoThing")]}
    manifest = _manifest({
        "/a": {"dep_hashes": {}, "app_wrap_keys": [], "is_stateful": False}
    })

    disk_cache._update_manifest_for_misses(
        manifest, cast(Any, miss_ctx), [page], complete_imports, root=tmp_path
    )

    written = json.loads((web / disk_cache._MANIFEST_FILE).read_text())
    assert disk_cache._deserialize_imports(written["all_imports"]) == complete_imports
