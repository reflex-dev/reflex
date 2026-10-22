"""Tests for the experimental disk-persisted incremental compile cache."""

import dataclasses
import datetime
import itertools
import json
import os
import sys
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, cast

import pytest
from reflex_base import constants
from reflex_base.components.component import Component
from reflex_base.environment import environment
from reflex_base.plugins import CompileContext, CompilerHooks, PageContext
from reflex_base.registry import RegistrationContext
from reflex_base.utils.format import to_snake_case
from reflex_base.utils.imports import ImportVar

import reflex as rx
from reflex.compiler import disk_cache, page_cache
from reflex.compiler.plugins import default_page_plugins
from reflex.compiler.utils import ContextsSnapshot
from reflex.state import BaseState, _frontend_schema_entries


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


def _compile(
    pages: Sequence[Any], app: Any = None, plugins: Sequence[Any] = ()
) -> CompileContext:
    from reflex.compiler import compiler

    # Reset like a full compile does before evaluating any page.
    compiler._reset_compile_registries(plugins)
    ctx = CompileContext(
        app=app,
        pages=pages,
        hooks=CompilerHooks(plugins=default_page_plugins(plugins=plugins)),
    )
    with ctx:
        ctx.compile()
    return ctx


def _unregister_state(cls: type[BaseState]) -> None:
    """Drop a state class from the registries, like the daemon registry reset.

    Lets a page evaluation re-define the same-named class in this process,
    mirroring what happens in the fork child between hot reloads.

    Args:
        cls: The state class to unregister.
    """
    from reflex_base.registry import RegistrationContext

    import reflex.istate.dynamic as istate_dynamic
    from reflex.state import all_base_state_classes

    ctx = RegistrationContext.ensure_context()
    full_name = cls.get_full_name()
    ctx.base_states.pop(full_name, None)
    parent = cls.get_parent_state()
    if parent is not None:
        ctx.base_state_substates.get(parent.get_full_name(), set()).discard(cls)
    all_base_state_classes.pop(full_name, None)
    if getattr(istate_dynamic, cls.__name__, None) is cls:
        delattr(istate_dynamic, cls.__name__)


@pytest.mark.parametrize("edited_module", ["state", "helper"])
def test_imported_state_edit_rebuilds_the_contexts(
    tmp_path, monkeypatch, edited_module
):
    """A module-level state edit rebuilds the contexts, not every page.

    The edited state's module (or a helper it imports) is an input of the
    contexts file; the pages that read the state recompile through their own
    recorded dependencies.
    """
    _use_tmp_web_dir(tmp_path, monkeypatch)
    source = tmp_path / "state_view.py"
    helper_source = tmp_path / "state_helper.py"
    helper_source.write_text("DEFAULT = 'old'\n")
    helper = ModuleType("cache_review_state_helper")
    helper.__file__ = str(helper_source)
    helper.__dict__["DEFAULT"] = "old"
    monkeypatch.setitem(sys.modules, helper.__name__, helper)
    code = (
        "import reflex as rx\n"
        "from cache_review_state_helper import DEFAULT\n"
        "class ImportedState(rx.State):\n"
        "    value: str = DEFAULT\n"
        "def index():\n"
        "    return rx.el.div(ImportedState.value)\n"
    )

    def load(source_code: str) -> ModuleType:
        """Execute the state module, as importing the app does.

        Args:
            source_code: The module source.

        Returns:
            The module.
        """
        source.write_text(source_code)
        module = ModuleType("cache_review_state_view")
        module.__file__ = str(source)
        monkeypatch.setitem(sys.modules, module.__name__, module)
        exec(compile(source_code, str(source), "exec"), module.__dict__)
        return module

    module = load(code)
    try:
        app = rx.App()
        app.add_page(module.index, route="/state")
        app.add_page(_page_a, route="/a")
        pages = list(app._unevaluated_pages.values())
        ctx = _compile(pages, app)
        assert not ctx.stateful_routes
        _stub_externals(app, monkeypatch)
        disk_cache.write_manifest(ctx, pages, ctx.all_imports, root=tmp_path)
        # The edit, then a fresh import of the app, as the daemon child does.
        _unregister_state(module.ImportedState)
        if edited_module == "state":
            module = load(code.replace("= DEFAULT", "= 'new default'"))
        else:
            helper_source.write_text("DEFAULT = 'new default'\n")
            helper.__dict__["DEFAULT"] = "new default"
            module = load(code)
        app._unevaluated_pages["state"] = dataclasses.replace(
            app._unevaluated_pages["state"], component=module.index
        )
        captured = _capture_contexts(monkeypatch)
        assert (
            disk_cache.try_incremental_rebuild(
                app, compiler_plugins=[], prerender_routes=False, root=tmp_path
            )
            is True
        )
        [(initial, _, _)] = captured
        [values] = [
            values
            for name, values in initial.items()
            if name.endswith("imported_state")
        ]
        assert "new default" in json.dumps(values)
    finally:
        _unregister_state(module.ImportedState)


def test_new_import_time_state_rebuilds_the_contexts(tmp_path, monkeypatch):
    """A state a recompiled page's module newly imports reaches the contexts.

    Importing the app registers it before any page evaluates, so no page
    defines it; only comparing the import-time states sees it.
    """
    web = _use_tmp_web_dir(tmp_path, monkeypatch)
    app = rx.App()
    app.add_page(_page_a, route="/a")
    pages = list(app._unevaluated_pages.values())
    ctx = _compile(pages, app)
    _stub_externals(app, monkeypatch)
    disk_cache.write_manifest(ctx, pages, ctx.all_imports, root=tmp_path)
    manifest_path = web / disk_cache._MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text())
    _stale_dep(manifest, "a", str(tmp_path / "view.py"))
    manifest_path.write_text(json.dumps(manifest))
    # The edited page module now imports a module defining a new state.
    new_state: Any = type(
        "_ImportTimeState",
        (rx.State,),
        {"__annotations__": {"value": int}, "value": 3, "__module__": "fp_mod_x"},
    )
    captured = _capture_contexts(monkeypatch)
    try:
        assert (
            disk_cache.try_incremental_rebuild(
                app, compiler_plugins=[], prerender_routes=False, root=tmp_path
            )
            is True
        )
    finally:
        _unregister_state(new_state)
    [(initial, _, _)] = captured
    assert new_state.get_full_name() in initial


def test_imports_round_trip():
    imports = {
        "react": [ImportVar("useEffect"), ImportVar("Fragment", is_default=False)],
        "@emotion/react": [ImportVar("jsx", alias="j", install=False)],
    }
    restored = disk_cache._deserialize_imports(disk_cache._serialize_imports(imports))
    assert restored == imports


@pytest.mark.parametrize("kind", ["date", "pydantic"])
def test_manifest_serializes_state_defaults_like_contexts(tmp_path, monkeypatch, kind):
    """Persist state defaults that require Reflex's frontend serializer."""
    from reflex_base.utils.format import json_dumps

    _use_tmp_web_dir(tmp_path, monkeypatch)
    value = (
        datetime.date(2026, 9, 5)
        if kind == "date"
        else pytest.importorskip("pydantic").create_model(
            "AppSettings", theme=(str, "light")
        )()
    )
    state_slice = {
        "initial_state": {"state": {"value": value}},
        "client_storage": {},
    }
    manifest = _manifest({"/date": {"state_slice": state_slice}})
    disk_cache._write(manifest)
    loaded = disk_cache.load_manifest()
    assert loaded is not None
    assert loaded["pages"]["/date"]["state_slice"] == json.loads(
        json_dumps(state_slice)
    )


def test_manifest_write_failure_is_visible(tmp_path, monkeypatch, caplog):
    """A failed cache write must explain why subsequent reloads compile everything."""
    _use_tmp_web_dir(tmp_path, monkeypatch)
    pages = [_FakePage(route="/a", component=_page_a)]
    ctx = _compile(pages)

    def fail_write(manifest):
        """Simulate a failure writing the cache manifest.

        Raises:
            OSError: The cache cannot be persisted.
        """
        msg = "disk full"
        raise OSError(msg)

    monkeypatch.setattr(disk_cache, "_write", fail_write)
    with caplog.at_level("WARNING", logger=disk_cache.__name__):
        disk_cache.write_manifest(ctx, pages, ctx.all_imports, root=tmp_path)
    assert any("disk full" in record.getMessage() for record in caplog.records)


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


def _manifest(pages: dict[str, dict], root: Path | None = None, **overrides) -> dict:
    base = {
        "schema": disk_cache._SCHEMA,
        "root": str((root or Path.cwd()).resolve()),
        "reflex_version": page_cache._reflex_version(),
        "mode": environment.REFLEX_ENV_MODE.get().value,
        "files": {},
        "globals": {"reflex": page_cache._reflex_version()},
        "globals_absent": [],
        "all_imports": {},
        "pages": pages,
        "memo_files": {},
        "entry": {"path": None, "digest": None},
        "module_states": {"names": [], "files": [], "dynamic": []},
        "app_root": {"wraps": {}, "libraries": [], "memo_keys": []},
    }
    base.update(overrides)
    return base


def _stale_dep(manifest: dict, route: str, path: str) -> None:
    """Make ``route`` depend on ``path`` with a recorded entry that cannot match.

    Simulates an edit: the page's dependency set is rewritten to a file whose
    stored stat/hash no longer match the current content, so partitioning sees
    the page as a miss.

    Args:
        manifest: The manifest to mutate.
        route: The page route.
        path: The dependency path.
    """
    manifest["pages"][route]["deps"] = [path]
    manifest["files"][path] = ["stale-hash", 0, 0]


def _validator(manifest: dict) -> page_cache.FileValidator:
    return page_cache.FileValidator(manifest["files"])


def test_globals_mismatch_names_the_changed_input(tmp_path):
    m = _manifest(
        {"/a": {}, "/b": {}},
        root=tmp_path,
        globals_absent=[str(tmp_path / "rxconfig.py")],
    )
    assert (
        disk_cache.globals_mismatch(m, validator=_validator(m), root=tmp_path) is None
    )
    # a stale reflex version -> named versions
    reason = disk_cache.globals_mismatch(
        {**m, "reflex_version": "0.0.0-old"},
        validator=_validator(m),
        root=tmp_path,
    )
    assert reason is not None
    assert "0.0.0-old" in reason


def test_globals_mismatch_accepts_entrypoint_registration_edits(tmp_path):
    """An entry module that only changed its add_page calls is not global."""
    entry = tmp_path / "entry_app.py"
    entry.write_text(
        'import reflex as rx\napp = rx.App()\napp.add_page(a, route="/a")\n'
    )
    file_entry = page_cache.file_entry(str(entry))
    assert file_entry is not None
    m = _manifest(
        {},
        root=tmp_path,
        files={str(entry): list(file_entry)},
        globals={"reflex": page_cache._reflex_version(), f"app:{entry}": str(entry)},
        entry={"path": str(entry), "digest": page_cache.entrypoint_digest(str(entry))},
    )
    entry.write_text(
        'import reflex as rx\napp = rx.App()\napp.add_page(a, route="/a")\n'
        'app.add_page(b, route="/b")\n'
    )
    assert (
        disk_cache.globals_mismatch(m, validator=_validator(m), root=tmp_path) is None
    )
    entry.write_text("import reflex as rx\napp = rx.App(enable_state=False)\n")
    reason = disk_cache.globals_mismatch(m, validator=_validator(m), root=tmp_path)
    assert reason is not None
    assert "entry_app.py" in reason


def test_globals_mismatch_names_a_moved_project(tmp_path):
    """A manifest only describes the project directory that wrote it.

    Its file table holds absolute paths, so a copy of the project made with
    its ``.web`` would otherwise validate the original project's files.
    """
    m = _manifest({"/a": {}}, root=tmp_path / "original")
    reason = disk_cache.globals_mismatch(
        m, validator=_validator(m), root=tmp_path / "copy"
    )
    assert reason is not None
    assert "project root changed" in reason


def test_globals_mismatch_names_a_compile_mode_change(tmp_path, monkeypatch):
    """A development build's output must never be reused by a production build.

    Rendered files differ by mode (e.g. ``isDevMode`` in the contexts file), so
    the mode is part of the cache identity.
    """
    monkeypatch.setenv("REFLEX_ENV_MODE", "dev")
    m = _manifest({"/a": {}}, root=tmp_path)
    assert (
        disk_cache.globals_mismatch(m, validator=_validator(m), root=tmp_path) is None
    )
    monkeypatch.setenv("REFLEX_ENV_MODE", "prod")
    reason = disk_cache.globals_mismatch(m, validator=_validator(m), root=tmp_path)
    assert reason is not None
    assert "dev -> prod" in reason


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
    entry = page_cache.file_entry(str(theme))
    assert entry is not None
    m = _manifest(
        {"/a": {}},
        root=tmp_path,
        files={str(theme): entry},
        globals={"reflex": page_cache._reflex_version(), f"app:{theme}": str(theme)},
        # global files absent from this root at write time and still absent
        globals_absent=[str(tmp_path / "rxconfig.py")],
    )

    def mismatch() -> str | None:
        return disk_cache.globals_mismatch(m, validator=_validator(m), root=tmp_path)

    # nothing on disk changed -> match, regardless of what a re-recorded
    # app-import read set would look like in this process
    assert mismatch() is None
    # a stored input's content changed -> mismatch naming that file
    theme.write_text("PRIMARY = 'blue'")
    reason = mismatch()
    assert reason is not None
    assert "theme_config.py" in reason
    # restored content with a fresh mtime: hashed once, still a match
    theme.write_text("PRIMARY = 'red'")
    assert mismatch() is None
    # a stored global file appearing counts as a change too
    (tmp_path / "rxconfig.py").write_text("import reflex")
    reason = mismatch()
    assert reason is not None
    assert "rxconfig.py" in reason


def test_format_path_list_relativizes_and_truncates():
    root = Path("/proj")
    assert disk_cache.format_path_list({"/proj/a.py", "other"}, root) == "a.py, other"
    many = {f"/proj/{i}.py" for i in range(8)}
    out = disk_cache.format_path_list(many, root, limit=3)
    assert out == "0.py, 1.py, 2.py (+5 more)"


def test_partition_pages_detects_changed_source(tmp_path):
    pages = [
        _FakePage(route="/a", component=_page_a),
        _FakePage(route="/b", component=_page_b),
    ]
    x, y = tmp_path / "x.py", tmp_path / "y.py"
    x.write_text("X = 1\n")
    y.write_text("Y = 1\n")
    # /a depends on x.py, /b depends on y.py (each recorded in the file table).
    m = _manifest(
        {
            page.route: {
                "deps": [str(dep)],
                "registration": "recorded",
            }
            for page, dep in zip(pages, (x, y), strict=True)
        },
        files={
            str(x): page_cache.file_entry(str(x)),
            str(y): page_cache.file_entry(str(y)),
        },
    )
    assert disk_cache.partition_pages(pages, m, _validator(m), None) == []
    y.write_text("Y = 2\n")
    miss = disk_cache.partition_pages(pages, m, _validator(m), None)
    assert {p.route for p in miss} == {"/b"}
    # With the watcher's changed set, pages depending on none of the changed
    # paths are hits without touching the filesystem.
    assert disk_cache.partition_pages(pages, m, _validator(m), {str(x)}) == []
    miss = disk_cache.partition_pages(pages, m, _validator(m), {str(y)})
    assert {p.route for p in miss} == {"/b"}


def test_partition_pages_rebuilds_a_volatile_page_whatever_the_hint(tmp_path):
    """A volatile page misses even when the watcher reports only other files."""
    pages = [_FakePage(route="/a", component=_page_a)]
    x = tmp_path / "x.py"
    x.write_text("X = 1\n")
    m = _manifest(
        {"/a": {"deps": [str(x), page_cache.VOLATILE_DEP], "registration": "recorded"}},
        files={str(x): page_cache.file_entry(str(x))},
    )
    miss = disk_cache.partition_pages(pages, m, _validator(m), {str(tmp_path / "y.py")})
    assert [p.route for p in miss] == ["/a"]


def test_pages_mismatch_names_the_change(tmp_path):
    """The page registry is an input of every page, so any change is global."""
    pages = [
        _FakePage(route="/a", component=_page_a),
        _FakePage(route="/b", component=_page_b),
    ]
    registrations = {page.route: "recorded" for page in pages}
    m = _manifest({page.route: {"registration": "recorded"} for page in pages})
    assert disk_cache._pages_mismatch(pages, m, registrations) is None
    reason = disk_cache._pages_mismatch(pages[::-1], m, registrations)
    assert reason == "the page order changed"
    reason = disk_cache._pages_mismatch(
        [*pages, _FakePage(route="/c", component=_page_c)],
        m,
        {**registrations, "/c": "new"},
    )
    assert reason is not None
    assert "added /c" in reason
    reason = disk_cache._pages_mismatch(pages[:1], m, registrations)
    assert reason is not None
    assert "removed /b" in reason
    reason = disk_cache._pages_mismatch(pages, m, {**registrations, "/b": "retitled"})
    assert reason == "page '/b' was registered differently"


def test_incomplete_cache_miss_falls_back_without_adoption(tmp_path, monkeypatch):
    """A miss without page output must be compiled again by the full path."""
    _use_tmp_web_dir(tmp_path, monkeypatch)
    app = rx.App()
    app.add_page(_page_a, route="/a")
    pages = list(app._unevaluated_pages.values())
    route = next(page.route for page in pages if page.component is _page_a)
    ctx = _compile(pages, app)
    disk_cache.write_manifest(ctx, pages, ctx.all_imports, root=tmp_path)
    _stub_externals(app, monkeypatch)

    manifest_path = disk_cache._manifest_path()
    manifest = json.loads(manifest_path.read_text())
    _stale_dep(manifest, route, str(tmp_path / "changed.py"))
    manifest_path.write_text(json.dumps(manifest))

    original_compile = CompileContext.compile

    def compile_without_output(self, **kwargs):
        """Simulate a page that evaluates but cannot produce frontend output.

        Returns:
            The contexts produced before their output is removed.
        """
        result = original_compile(self, **kwargs)
        for page_ctx in self.compiled_pages.values():
            page_ctx.output_code = None
        return result

    monkeypatch.setattr(CompileContext, "compile", compile_without_output)

    assert (
        disk_cache.try_incremental_rebuild(
            app, compiler_plugins=[], prerender_routes=False, root=tmp_path
        )
        is False
    )


def test_absorb_preserves_page_order_for_app_wraps():
    """A later reused page must override an earlier recompiled page's wrap."""
    first = _FakePage(route="/first", component=_page_a)
    second = _FakePage(route="/second", component=_page_b)
    key = (1, "shared")
    first_wrap = rx.box("first")
    second_wrap = rx.box("second")
    first_ctx = PageContext(
        name="first",
        route=first.route,
        root_component=rx.box(),
        app_wrap_components={key: first_wrap},
    )
    second_ctx = PageContext(
        name="second",
        route=second.route,
        root_component=rx.box(),
        app_wrap_components={key: second_wrap},
    )
    reused = CompileContext(
        pages=[second],
        compiled_pages={second.route: second_ctx},
        app_wrap_components={key: second_wrap},
    )
    recompiled = CompileContext(
        pages=[first],
        compiled_pages={first.route: first_ctx},
        app_wrap_components={key: first_wrap},
    )

    reused.absorb(recompiled, [first, second])

    assert reused.app_wrap_components[key] is second_wrap


def test_write_and_load_manifest(tmp_path, monkeypatch):
    _use_tmp_web_dir(tmp_path, monkeypatch)
    monkeypatch.setenv("REFLEX_ENV_MODE", "dev")

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
    assert manifest["mode"] == "dev"
    assert set(manifest["pages"]) == {"/a", "/b", "/c"}
    for route in ("/a", "/b", "/c"):
        entry = manifest["pages"][route]
        # the manifest is pure bookkeeping: dep set + app-wrap keys + flags
        assert set(entry) == {
            "deps",
            "component_counts",
            "app_wraps",
            "registration",
            "is_stateful",
            "state_slice",
            "dynamic_claims",
            "memo_keys",
            "radix",
        }
        # these static pages register no new state and use no memos
        assert entry["is_stateful"] is False
        assert entry["state_slice"] is None
        assert entry["memo_keys"] == []
        assert entry["radix"] is False
        assert entry["dynamic_claims"] == []
        # every dependency has a file-table entry: [sha256, mtime_ns, size]
        for dep in entry["deps"]:
            digest, mtime_ns, size = manifest["files"][dep]
            assert len(digest) == 64
            assert mtime_ns > 0
            assert size > 0
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


def test_names_drawn_after_the_pages_never_repeat_import_time_names():
    """The post-page phase keeps the names the process drew before the compile.

    A module-level component draws its ref name at import; after the pages,
    the app root and runtime components draw more. Reseeding the import
    sequence would hand the same names out again.
    """
    from reflex_base.vars.base import (
        get_unique_variable_name,
        reset_unique_variable_names,
    )

    reset_unique_variable_names()
    import_names = {get_unique_variable_name() for _ in range(3)}
    _compile([_FakePage(route="/a", component=_page_a)])
    after = {get_unique_variable_name() for _ in range(50)}
    assert not after & import_names
    # And the post-page sequence is the same on every compile.
    _compile([_FakePage(route="/b", component=_page_b)])
    assert {get_unique_variable_name() for _ in range(50)} == after


_CONTEXTS_STUB = "// contexts stub"


_TEST_STATE_MODULES = (__name__, "fp_mod_x", "cache_review_state_view")


def _scoped_contexts_snapshot(app) -> ContextsSnapshot | None:
    """A ``_contexts_snapshot`` limited to the states this test file defines.

    Same shape and serialization as the real snapshot, but each test state is
    compiled standalone instead of walking the whole root state tree, which
    would pick up unrelated (and sometimes broken) state classes collected
    from other test modules. Schema entries only read class metadata, so they
    still cover the whole tree.

    Args:
        app: The app being compiled.

    Returns:
        The contexts snapshot for this file's states, or None when the app has
        no state tree.
    """
    if app is None or app._state is None:
        return None
    context = RegistrationContext.ensure_context()
    initial, storage, _ = _states_snapshot(
        cls
        for cls in list(context.base_states.values())
        if cls.__module__ in _TEST_STATE_MODULES
    )
    return initial, storage, _frontend_schema_entries(app._state, context)


def _states_snapshot(classes: Iterable[type[BaseState]]) -> ContextsSnapshot:
    """Compile a contexts snapshot from the given states, each standalone.

    Args:
        classes: The states to compile.

    Returns:
        The contexts snapshot of those states.
    """
    from reflex.compiler import utils as compiler_utils

    context = RegistrationContext.ensure_context()
    initial: dict[str, Any] = {}
    storage: dict[str, dict[str, Any]] = {}
    schema_entries: dict[str, list[Any]] = {}
    for cls in classes:
        initial.update(compiler_utils.compile_state(cls))
        for kind, entries in compiler_utils.compile_client_storage(cls).items():
            storage.setdefault(kind, {}).update(entries)
        schema_entries.update(_frontend_schema_entries(cls, context))
    return initial, storage, schema_entries


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
        lambda state, theme, **kwargs: (
            compiler_utils.get_context_path(),
            _CONTEXTS_STUB,
        ),
    )
    monkeypatch.setattr(disk_cache, "_contexts_snapshot", _scoped_contexts_snapshot)
    monkeypatch.setattr(fs, "update_react_router_config", lambda **k: None)
    monkeypatch.setattr(fs, "update_entry_client", lambda *a, **k: None)
    monkeypatch.setattr(fs, "initialize_vite_config", lambda: None)
    # The full compile that preceded the rebuild wrote the bundled libraries.
    libs_path, libs_code = compiler_utils._compile_bundled_libraries()
    libs_file = compiler_utils.resolve_path_of_web_dir(libs_path)
    libs_file.parent.mkdir(parents=True, exist_ok=True)
    libs_file.write_text(libs_code)


def _page_local_state() -> Component:
    class CacheLocalState(rx.State):
        value: int = 0

    return rx.el.div(CacheLocalState.value)


def _page_local_component_default() -> Component:
    class CacheComponentDefaultState(rx.State):
        scroller: rx.Field[rx.Component] = rx.field(default_factory=rx.auto_scroll)

    return rx.el.div(CacheComponentDefaultState.scroller)


def test_manifest_state_slice_matches_the_compiled_contexts_snapshot(
    tmp_path, monkeypatch
):
    """State defaults in the manifest must use the contexts compilation values."""
    _use_tmp_web_dir(tmp_path, monkeypatch)
    app = rx.App()
    app.add_page(_page_local_component_default, route="/stateful")
    pages = list(app._unevaluated_pages.values())
    ctx = _compile(pages, app)
    route = next(
        page.route for page in pages if page.component is _page_local_component_default
    )
    defined_states = ctx.stateful_routes[route]
    registry = RegistrationContext.ensure_context()
    snapshot = _states_snapshot(registry.base_states[name] for name in defined_states)
    expected = json.loads(
        disk_cache.json_dumps(disk_cache._state_slice(defined_states, *snapshot))
    )

    try:
        disk_cache.write_manifest(
            ctx,
            pages,
            ctx.all_imports,
            root=tmp_path,
            contexts_snapshot=snapshot,
        )
        manifest = disk_cache.load_manifest()
        assert manifest is not None
        assert manifest["pages"][route]["state_slice"] == expected
    finally:
        for state_name in defined_states:
            _unregister_state(registry.base_states[state_name])


def test_post_evaluation_fallback_hands_over_the_evaluated_pages(tmp_path, monkeypatch):
    """A fallback decided after evaluating miss pages returns those pages.

    Evaluating a page registers the states it defines. Re-evaluating it in the
    same process (as an in-process full compile would) registers a locally
    defined state under a collision suffix (``CacheLocalState_0``) while the
    backend, which evaluates the page once, knows it as ``CacheLocalState``.
    The full compile therefore has to reuse this evaluation, not repeat it.
    """
    from reflex_base.registry import RegistrationContext

    web = _use_tmp_web_dir(tmp_path, monkeypatch)
    app = rx.App()
    app.add_page(_page_a, route="/a")
    app.add_page(_page_local_state, route="/s")
    _stub_externals(app, monkeypatch)
    pages = list(app._unevaluated_pages.values())
    route_s = pages[1].route
    ctx = _compile(pages, app)
    defined = ctx.stateful_routes[route_s]
    assert defined[0].endswith("cache_local_state")
    disk_cache.write_manifest(ctx, pages, ctx.all_imports, root=tmp_path)

    def forget_local_states() -> None:
        """Drop the page-defined states, as the daemon's child reset does."""
        registry = RegistrationContext.ensure_context()
        for name in defined:
            cls = registry.base_states.get(name)
            if cls is not None:
                _unregister_state(cls)

    forget_local_states()
    try:
        # The manifest recorded another app-wrap set for /s; only a full
        # compile can rebuild the app root.
        manifest_path = web / disk_cache._MANIFEST_FILE
        manifest = json.loads(manifest_path.read_text())
        manifest["app_root"]["wraps"] = {}
        _stale_dep(manifest, route_s, str(tmp_path / "demo.md"))
        manifest_path.write_text(json.dumps(manifest))

        result = disk_cache.try_incremental_rebuild(
            app, compiler_plugins=[], prerender_routes=False, root=tmp_path
        )
        assert isinstance(result, CompileContext)
        assert set(result.compiled_pages) == {route_s}
        assert result.stateful_routes[route_s] == defined
    finally:
        forget_local_states()


def _capture_contexts(monkeypatch) -> list[Any]:
    """Record the snapshots handed to ``compile_contexts``.

    Args:
        monkeypatch: The pytest monkeypatch fixture.

    Returns:
        The list the snapshots are appended to.
    """
    from reflex.compiler import utils as compiler_utils

    captured: list[Any] = []

    def fake_compile_contexts(state, theme, *, contexts_snapshot, **kwargs):
        captured.append(contexts_snapshot)
        return compiler_utils.get_context_path(), _CONTEXTS_STUB

    monkeypatch.setattr(
        "reflex.compiler.compiler.compile_contexts", fake_compile_contexts
    )
    return captured


def _page_flip() -> Component:
    return rx.el.div(rx.el.p(_fp_state("_FlipState").value), _footer())


def test_page_becoming_stateful_rebuilds_incrementally(tmp_path, monkeypatch):
    """A page that starts defining states needs only its contexts slice.

    The app root depends on whether the app has state at all, which ``rx.App``
    decides, not on which pages define states.
    """
    web = _use_tmp_web_dir(tmp_path, monkeypatch)
    app = rx.App()
    app.add_page(_page_a, route="/a")
    app.add_page(_page_flip, route="/s")
    pages = list(app._unevaluated_pages.values())
    route_s = pages[1].route
    ctx = _compile(pages, app)
    defined = ctx.stateful_routes[route_s]
    _stub_externals(app, monkeypatch)
    disk_cache.write_manifest(ctx, pages, ctx.all_imports, root=tmp_path)
    _unregister_state(_FP_HOLDER.pop("_FlipState"))
    manifest_path = web / disk_cache._MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text())
    # Recorded before the edit that made /s define its state.
    manifest["pages"][route_s].update(is_stateful=False, state_slice=None)
    _stale_dep(manifest, route_s, str(tmp_path / "view.py"))
    manifest_path.write_text(json.dumps(manifest))
    captured = _capture_contexts(monkeypatch)
    try:
        assert (
            disk_cache.try_incremental_rebuild(
                app, compiler_plugins=[], prerender_routes=False, root=tmp_path
            )
            is True
        )
    finally:
        _unregister_state(_FP_HOLDER.pop("_FlipState"))
    [(initial, _, _)] = captured
    assert set(defined) <= set(initial)
    refreshed = json.loads(manifest_path.read_text())
    assert refreshed["pages"][route_s]["is_stateful"] is True


def _drop_page_state(
    tmp_path,
    monkeypatch,
    gone: str,
    compile_contexts: Callable[..., Any] | None = None,
    install: Callable[[Any], None] | None = None,
) -> tuple[Any, list[Any], dict[str, Any]]:
    """Rebuild a page that defined ``gone`` before an edit and no state after it.

    Args:
        tmp_path: The project root.
        monkeypatch: The pytest monkeypatch fixture.
        gone: The full name of the state the page stopped defining.
        compile_contexts: Replaces ``compile_contexts`` after the capture.
        install: Receives the imports whose packages the rebuild installs.

    Returns:
        The rebuild result, the captured contexts snapshots, and the manifest.
    """
    web = _use_tmp_web_dir(tmp_path, monkeypatch)
    app = rx.App()
    app.add_page(_page_a, route="/a")
    pages = list(app._unevaluated_pages.values())
    ctx = _compile(pages, app)
    _stub_externals(app, monkeypatch)
    disk_cache.write_manifest(ctx, pages, ctx.all_imports, root=tmp_path)
    manifest_path = web / disk_cache._MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text())
    manifest["pages"]["a"].update(
        is_stateful=True,
        state_slice={
            "initial_state": {gone: {"value_rx_state_": 0}},
            "client_storage": {},
            "schema": {gone: [gone, [["value", "int"]], [], []]},
        },
    )
    _stale_dep(manifest, "a", str(tmp_path / "view.py"))
    manifest_path.write_text(json.dumps(manifest))
    captured = _capture_contexts(monkeypatch)
    if compile_contexts is not None:
        monkeypatch.setattr(
            "reflex.compiler.compiler.compile_contexts", compile_contexts
        )
    if install is not None:
        monkeypatch.setattr(app, "_get_frontend_packages", install)
    result = disk_cache.try_incremental_rebuild(
        app, compiler_plugins=[], prerender_routes=False, root=tmp_path
    )
    return result, captured, json.loads(manifest_path.read_text())


#: A local state the page defined; no other page can use it.
_GONE_LOCAL = "reflex___state____state.reflex___istate___dynamic____gone_state"


def test_page_dropping_its_states_rebuilds_contexts(tmp_path, monkeypatch):
    """A page that stops defining states takes its slice out of the contexts."""
    result, captured, refreshed = _drop_page_state(tmp_path, monkeypatch, _GONE_LOCAL)
    assert result is True
    [(initial, _, schema_entries)] = captured
    assert _GONE_LOCAL not in initial
    assert _GONE_LOCAL not in schema_entries
    assert refreshed["pages"]["a"]["is_stateful"] is False


def test_page_dropping_a_shared_state_falls_back(tmp_path, monkeypatch):
    """A module state the page stops importing may still serve unchanged pages.

    Those pages recorded no slice for it, so only a full compile keeps it.
    """
    gone = "reflex___state____state.shared_module___shared_state"
    result, captured, _ = _drop_page_state(tmp_path, monkeypatch, gone)
    assert isinstance(result, CompileContext)
    assert captured == []


def test_contexts_rebuild_installs_the_packages_state_defaults_import(
    tmp_path, monkeypatch
):
    """A component-valued state default can bring a package no page imports."""
    from reflex.compiler import utils as compiler_utils

    def compile_contexts(state, theme, *, contexts_snapshot, component_imports):
        component_imports.setdefault("state-only-package", []).append(
            ImportVar(tag="Widget")
        )
        return compiler_utils.get_context_path(), _CONTEXTS_STUB

    installed: list[Any] = []
    result, _, refreshed = _drop_page_state(
        tmp_path, monkeypatch, _GONE_LOCAL, compile_contexts, installed.append
    )
    assert result is True
    assert "state-only-package" in installed[-1]
    assert "state-only-package" in refreshed["all_imports"]


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

    from reflex.utils.telemetry_accounting import _count_components

    assert app._cached_component_counts == _count_components(
        page.root_component for page in ctx.compiled_pages.values()
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
    _stale_dep(manifest, edited_route, str(tmp_path / "view.py"))
    manifest_path.write_text(json.dumps(manifest))

    assert (
        disk_cache.try_incremental_rebuild(
            app, compiler_plugins=[], prerender_routes=False, root=tmp_path
        )
        is True
    )

    assert edited_route in app._pages
    assert edited_route in app._evaluated_pages

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


def test_stateful_miss_rewrites_contexts_from_manifest_slices(tmp_path, monkeypatch):
    """A stateful miss rewrites contexts without re-evaluating any hit page.

    Hit pages' evaluation-time states are not in this process's state tree;
    their recorded contribution (``state_slice``) is handed to
    ``compile_contexts`` instead, so the rewritten contexts file keeps every
    state and no unchanged page is evaluated.
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
    _stale_dep(manifest, stateful_route, str(tmp_path / "view.py"))
    hit_slice = {
        "initial_state": {"root.hit_state": {"count": 0}},
        "client_storage": {
            "cookies": {"root.hit_state.token_rx_field_": {"name": "t"}},
            "local_storage": {},
            "session_storage": {},
        },
        "schema": {"root.hit_state": ["root.hit_state", [["count", "int"]], [], []]},
    }
    manifest["pages"][hit_route]["is_stateful"] = True
    manifest["pages"][hit_route]["state_slice"] = hit_slice
    manifest_path.write_text(json.dumps(manifest))

    reevaluated: list[str] = []
    monkeypatch.setattr(
        app, "_compile_page", lambda route, **k: reevaluated.append(route)
    )
    captured: list[Any] = []

    def fake_compile_contexts(state, theme, *, contexts_snapshot, **kwargs):
        captured.append(contexts_snapshot)
        return compiler_utils.get_context_path(), _CONTEXTS_STUB

    monkeypatch.setattr(
        "reflex.compiler.compiler.compile_contexts", fake_compile_contexts
    )

    assert (
        disk_cache.try_incremental_rebuild(
            app, compiler_plugins=[], prerender_routes=False, root=tmp_path
        )
        is True
    )
    # No page is re-evaluated; the hit page's stored slice is merged instead.
    assert reevaluated == []
    [(initial, storage, schema_entries)] = captured
    assert initial["root.hit_state"] == {"count": 0}
    assert storage["cookies"]["root.hit_state.token_rx_field_"] == {"name": "t"}
    assert schema_entries["root.hit_state"] == hit_slice["schema"]["root.hit_state"]
    out_path = compiler_utils.resolve_path_of_web_dir(compiler_utils.get_context_path())
    assert out_path.read_text(encoding="utf-8") == _CONTEXTS_STUB


def _slice_fingerprint(
    names: list[str],
    initial: dict[str, Any],
    storage: dict[str, dict[str, Any]],
    schema_entries: dict[str, list[Any]],
) -> str:
    return disk_cache._slice_digest(
        disk_cache._state_slice(names, initial, storage, schema_entries)
    )


def test_contexts_fingerprint_sensitivity():
    initial = {"root.s_one": {"value": ""}, "root.s_two": {"count": 0}}
    storage = {
        "cookies": {"root.s_one.token_rx_field_": {"name": "t"}},
        "local_storage": {},
        "session_storage": {},
    }
    schema = {
        "root.s_one": ["root.s_one", [["value", "str"]], [], []],
        "root.s_two": ["root.s_two", [["count", "int"]], [], []],
    }
    base = _slice_fingerprint(["root.s_one"], initial, storage, schema)
    # Stable across equal inputs and insensitive to name order.
    assert _slice_fingerprint(["root.s_one"], dict(initial), storage, schema) == base
    both = _slice_fingerprint(["root.s_one", "root.s_two"], initial, storage, schema)
    assert (
        _slice_fingerprint(["root.s_two", "root.s_one"], initial, storage, schema)
        == both
    )
    # Sensitive to which states, their initial values, their client storage
    # and their frontend schema.
    assert _slice_fingerprint(["root.s_two"], initial, storage, schema) != base
    assert (
        _slice_fingerprint(
            ["root.s_one"], {"root.s_one": {"value": "x"}}, storage, schema
        )
        != base
    )
    assert (
        _slice_fingerprint(
            ["root.s_one"],
            initial,
            {"cookies": {}, "local_storage": {}, "session_storage": {}},
            schema,
        )
        != base
    )
    assert (
        _slice_fingerprint(
            ["root.s_one"],
            initial,
            storage,
            {"root.s_one": ["root.s_one", [["value", "str"]], [], ["touch"]]},
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
    stored_fp = manifest["pages"][stateful_route]["state_slice"]
    assert stored_fp  # the compile recorded the page's state config
    # Make the stateful page a miss; mark the hit page stateful so a contexts
    # rebuild (if wrongly triggered) would have to re-evaluate it.
    _stale_dep(manifest, stateful_route, str(tmp_path / "view.py"))
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
    assert refreshed["pages"][stateful_route]["state_slice"] == stored_fp
    _unregister_state(_FP_HOLDER.pop("cls"))


_SCHEMA_MISS_HANDLER = {"handler": False}


def _fp_state(name: str, *, handler: bool = False) -> Any:
    """Define a test state in the ``fp_mod_x`` module, as a page evaluation does.

    Args:
        name: The class name.
        handler: Whether the state defines an event handler.

    Returns:
        The state class, also kept in ``_FP_HOLDER`` under ``name``.
    """
    namespace: dict[str, Any] = {
        "__annotations__": {"value": str},
        "value": "",
        "__module__": "fp_mod_x",
    }
    if handler:

        def touch(self):
            """A handler that only exists in the edited state."""

        namespace["touch"] = touch
    state_cls = type(name, (rx.State,), namespace)
    _FP_HOLDER[name] = state_cls
    return state_cls


def _page_schema_miss() -> Component:
    state_cls = _fp_state("_SchemaMissState", handler=_SCHEMA_MISS_HANDLER["handler"])
    return rx.el.div(rx.el.p(state_cls.value), _footer())


def _page_schema_hit() -> Component:
    return rx.el.div(rx.el.p(_fp_state("_SchemaHitState").value), _footer())


def _schema_pages(tmp_path, monkeypatch):
    """Compile a stateful miss page and a stateful hit page, then reset states.

    Args:
        tmp_path: The project root.
        monkeypatch: The pytest monkeypatch fixture.

    Returns:
        The app, the manifest path, the miss route and the full-tree schema.
    """
    web = _use_tmp_web_dir(tmp_path, monkeypatch)
    app = rx.App()
    app.add_page(_page_schema_miss, route="/miss")
    app.add_page(_page_schema_hit, route="/hit")
    pages = list(app._unevaluated_pages.values())
    ctx = _compile(pages, app=app)
    assert app._state is not None
    full_schema = app._state._to_frontend_schema()
    _stub_externals(app, monkeypatch)
    disk_cache.write_manifest(ctx, pages, ctx.all_imports, root=tmp_path)
    manifest_path = web / disk_cache._MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text())
    miss_route = pages[0].route
    _stale_dep(manifest, miss_route, str(tmp_path / "view.py"))
    manifest_path.write_text(json.dumps(manifest))
    # The daemon child starts without the states its pages define.
    for name in ("_SchemaMissState", "_SchemaHitState"):
        _unregister_state(_FP_HOLDER.pop(name))
    return app, manifest_path, miss_route, full_schema


def test_contexts_rebuild_hashes_the_schema_of_cached_states(tmp_path, monkeypatch):
    """A contexts rebuild hashes the hit pages' cached states into ``stateSchema``.

    The backend evaluates every stateful page, so its schema covers states
    that this process never evaluated. A schema of the live tree alone would
    make every frontend look stale to a matching backend.
    """
    from reflex.compiler import compiler
    from reflex.compiler import utils as compiler_utils

    compile_contexts = compiler.compile_contexts
    app, manifest_path, miss_route, full_schema = _schema_pages(tmp_path, monkeypatch)
    manifest = json.loads(manifest_path.read_text())
    manifest["pages"][miss_route]["state_slice"] = None
    manifest_path.write_text(json.dumps(manifest))
    monkeypatch.setattr(compiler, "compile_contexts", compile_contexts)

    try:
        assert (
            disk_cache.try_incremental_rebuild(
                app, compiler_plugins=[], prerender_routes=False, root=tmp_path
            )
            is True
        )
    finally:
        _unregister_state(_FP_HOLDER.pop("_SchemaMissState"))
    contexts = compiler_utils.resolve_path_of_web_dir(
        compiler_utils.get_context_path()
    ).read_text(encoding="utf-8")
    assert f"export const stateSchema = {json.dumps(full_schema)}" in contexts


def test_handler_only_state_edit_rebuilds_contexts(tmp_path, monkeypatch):
    """An event handler added to a recompiled page's state rebuilds contexts."""
    from reflex.compiler import utils as compiler_utils

    app, _, _, _ = _schema_pages(tmp_path, monkeypatch)
    out_path = compiler_utils.resolve_path_of_web_dir(compiler_utils.get_context_path())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("// pre-existing contexts", encoding="utf-8")
    monkeypatch.setitem(_SCHEMA_MISS_HANDLER, "handler", True)

    try:
        assert (
            disk_cache.try_incremental_rebuild(
                app, compiler_plugins=[], prerender_routes=False, root=tmp_path
            )
            is True
        )
    finally:
        _unregister_state(_FP_HOLDER.pop("_SchemaMissState"))
    assert out_path.read_text(encoding="utf-8") == _CONTEXTS_STUB


_COMPONENT_DEFAULT = {"recharts": False}


def _page_component_default() -> Component:
    def default() -> Component:
        if _COMPONENT_DEFAULT["recharts"]:
            return rx.recharts.line_chart(rx.recharts.line(data_key="v"))
        return rx.el.div("plain")

    state_cls: Any = type(
        "_ComponentDefaultState",
        (rx.State,),
        {
            "__annotations__": {"comp": rx.Field[rx.Component]},
            "comp": rx.field(default_factory=default),
            "__module__": "fp_mod_x",
        },
    )
    _FP_HOLDER["_ComponentDefaultState"] = state_cls
    return rx.el.div(rx.box(state_cls.comp))


def test_state_default_from_new_library_falls_back(tmp_path, monkeypatch):
    """A component default from a new library needs a full compile.

    The contexts reference the library through ``window.__reflex``, which the
    app root and bundled-library file provide; only a full compile rewrites
    them, and it adopts the pages the attempt evaluated.
    """
    from reflex.compiler import compiler

    compile_contexts = compiler.compile_contexts
    web = _use_tmp_web_dir(tmp_path, monkeypatch)
    app = rx.App()
    app.add_page(_page_component_default, route="/dyn")
    pages = list(app._unevaluated_pages.values())
    ctx = _compile(pages, app=app)
    _stub_externals(app, monkeypatch)
    disk_cache.write_manifest(ctx, pages, ctx.all_imports, root=tmp_path)
    manifest_path = web / disk_cache._MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text())
    _stale_dep(manifest, pages[0].route, str(tmp_path / "view.py"))
    manifest_path.write_text(json.dumps(manifest))
    _unregister_state(_FP_HOLDER.pop("_ComponentDefaultState"))
    monkeypatch.setitem(_COMPONENT_DEFAULT, "recharts", True)
    monkeypatch.setattr(compiler, "compile_contexts", compile_contexts)
    try:
        result = disk_cache.try_incremental_rebuild(
            app, compiler_plugins=[], prerender_routes=False, root=tmp_path
        )
    finally:
        _unregister_state(_FP_HOLDER.pop("_ComponentDefaultState"))
    assert isinstance(result, CompileContext)
    assert set(result.compiled_pages) == {pages[0].route}


def test_unchanged_component_default_reuses_the_contexts(tmp_path, monkeypatch):
    """A recompiled page with the same component default keeps the contexts.

    The recorded slice holds the default serialized the way the contexts file
    holds it, whichever libraries were bundled when the slice was taken.
    """
    from reflex.compiler import compiler
    from reflex.compiler import utils as compiler_utils

    web = _use_tmp_web_dir(tmp_path, monkeypatch)
    monkeypatch.setitem(_COMPONENT_DEFAULT, "recharts", True)
    app = rx.App()
    app.add_page(_page_component_default, route="/dyn")
    pages = list(app._unevaluated_pages.values())
    ctx = _compile(pages, app=app)
    _stub_externals(app, monkeypatch)
    disk_cache.write_manifest(ctx, pages, ctx.all_imports, root=tmp_path)
    manifest_path = web / disk_cache._MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text())
    _stale_dep(manifest, pages[0].route, str(tmp_path / "view.py"))
    manifest_path.write_text(json.dumps(manifest))
    _unregister_state(_FP_HOLDER.pop("_ComponentDefaultState"))
    # A fresh process has not bundled the default's library yet.
    compiler._reset_compile_registries([])
    out_path = compiler_utils.resolve_path_of_web_dir(compiler_utils.get_context_path())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("// pre-existing contexts", encoding="utf-8")
    try:
        assert (
            disk_cache.try_incremental_rebuild(
                app, compiler_plugins=[], prerender_routes=False, root=tmp_path
            )
            is True
        )
    finally:
        _unregister_state(_FP_HOLDER.pop("_ComponentDefaultState"))
    assert out_path.read_text(encoding="utf-8") == "// pre-existing contexts"


def _app_root_file(web: Path) -> Path:
    return web / constants.Dirs.PAGES / constants.PageNames.APP_ROOT


class _WrappedDiv(rx.el.Div):
    """A div that requires an app-level wrap no other test page provides."""

    @staticmethod
    def _get_app_wrap_components() -> dict[tuple[int, str], Component]:
        """Declare the extra app wrap.

        Returns:
            The app wraps this component requires.
        """
        return {(55, "TestWrap"): rx.el.section(class_name="test-wrap")}


_WRAP_EDIT = {"wrap": False, "state": False}


def _page_wrap_edit() -> Component:
    if _WRAP_EDIT["wrap"]:
        return rx.el.div(_WrappedDiv.create("wrapped"), _footer())
    if _WRAP_EDIT["state"]:
        return rx.el.div(rx.el.p(_fp_state("_WrapEditState").value), _footer())
    return rx.el.div("plain", _footer())


def _page_state_provider() -> Component:
    return rx.el.div(rx.el.p(_fp_state("_ProviderState").value), _footer())


def _root_rebuild(
    tmp_path, monkeypatch, *, reversed_wraps: list[str] | None = None, **edit
) -> tuple[Any, Path, str]:
    """Fully compile a stateful page and a plain page, then edit the plain one.

    Args:
        tmp_path: The project root.
        monkeypatch: The pytest monkeypatch fixture.
        reversed_wraps: When given, the app root's wraps are recorded in
            reverse order, which is appended to it.
        edit: The ``_WRAP_EDIT`` flags the edit turns on.

    Returns:
        The rebuild result, the app root file and its content before the edit.
    """
    from reflex.compiler import compiler

    try:
        web = _use_tmp_web_dir(tmp_path, monkeypatch)
        app = rx.App()
        app.add_page(_page_state_provider, route="/s")
        app.add_page(_page_wrap_edit, route="/p")
        pages = list(app._unevaluated_pages.values())
        ctx = _compile(pages, app=app)
        _stub_externals(app, monkeypatch)
        root_path, root_code = compiler.compile_app_root(
            *compiler._build_app_root(app, ctx.app_wrap_components, ctx)
        )
        Path(root_path).parent.mkdir(parents=True, exist_ok=True)
        Path(root_path).write_text(root_code)
        disk_cache.write_manifest(ctx, pages, ctx.all_imports, root=tmp_path)
        manifest_path = web / disk_cache._MANIFEST_FILE
        manifest = json.loads(manifest_path.read_text())
        if reversed_wraps is not None:
            wraps = manifest["app_root"]["wraps"]
            assert len(wraps) > 1
            manifest["app_root"]["wraps"] = dict(reversed(wraps.items()))
            reversed_wraps.extend(manifest["app_root"]["wraps"])
        _stale_dep(manifest, pages[1].route, str(tmp_path / "view.py"))
        manifest_path.write_text(json.dumps(manifest))
        # The daemon child starts without the states its pages define.
        _unregister_state(_FP_HOLDER.pop("_ProviderState"))
        for flag, value in edit.items():
            monkeypatch.setitem(_WRAP_EDIT, flag, value)
        result = disk_cache.try_incremental_rebuild(
            app, compiler_plugins=[], prerender_routes=False, root=tmp_path
        )
    finally:
        for name in ("_ProviderState", "_WrapEditState"):
            if (cls := _FP_HOLDER.pop(name, None)) is not None:
                _unregister_state(cls)
    return result, _app_root_file(web), root_code


def test_page_gaining_a_provided_wrap_reuses_the_app_root(tmp_path, monkeypatch):
    """The app root depends on the union of wraps, not on each page's own set."""
    result, root_file, before = _root_rebuild(tmp_path, monkeypatch, state=True)
    assert result is True
    assert root_file.read_text() == before


def test_app_root_with_reordered_wraps_falls_back(tmp_path, monkeypatch):
    """Wraps of one priority nest in page order, so another order is a change."""
    recorded: list[str] = []
    result, root_file, before = _root_rebuild(
        tmp_path, monkeypatch, reversed_wraps=recorded
    )
    assert isinstance(result, CompileContext)
    assert root_file.read_text() == before


def test_page_bringing_a_new_wrap_falls_back(tmp_path, monkeypatch):
    """A wrap no recorded page provides needs the app root rebuilt in full.

    The attempt hands over the page it evaluated; the root on disk is left
    for the full compile to replace.
    """
    result, root_file, before = _root_rebuild(tmp_path, monkeypatch, wrap=True)
    assert isinstance(result, CompileContext)
    assert set(result.compiled_pages) == {"p"}
    assert root_file.read_text() == before


_COLLIDE = {"one": 0, "two": 0, "two_extra": False, "two_unique": False}


def _page_collide_one() -> Component:
    _COLLIDE["one"] += 1

    class CollideState(rx.State):
        one: int = 1

    return rx.el.div(rx.el.p(CollideState.one), _footer())


def _page_collide_two() -> Component:
    _COLLIDE["two"] += 1

    class CollideState(rx.State):
        two: int = 2

    def define_extra() -> None:
        class CollideState(rx.State):
            extra: int = 3

    def define_unique() -> None:
        class UniqueToTwoState(rx.State):
            unique: int = 4

    if _COLLIDE["two_extra"]:
        define_extra()
    if _COLLIDE["two_unique"]:
        define_unique()
    return rx.el.div(rx.el.p(CollideState.two), _footer())


def _rebuild_second_page(
    tmp_path,
    monkeypatch,
    first: Callable[[], Component],
    second: Callable[[], Component],
    *,
    predict: bool,
    markers: tuple[str, ...],
    prepare: Callable[[], None],
) -> tuple[Any, list[str], list[str]]:
    """Compile two pages, then rebuild the second as if its module changed.

    Args:
        tmp_path: The project root.
        monkeypatch: The pytest monkeypatch fixture.
        first: The first page.
        second: The second page.
        predict: Whether the rebuild predicts dynamic state names.
        markers: Name parts of the dynamic states the pages define, dropped
            before the rebuild like the daemon child's fresh import does.
        prepare: Resets page bookkeeping before the rebuild.

    Returns:
        The rebuild result, the second page's states before the edit, and its
        recorded states after the rebuild.
    """
    web = _use_tmp_web_dir(tmp_path, monkeypatch)
    app = rx.App()
    app.add_page(first, route="/one")
    app.add_page(second, route="/two")
    pages = list(app._unevaluated_pages.values())
    ctx = _compile(pages, app=app)
    second_states = ctx.stateful_routes[pages[1].route]
    _stub_externals(app, monkeypatch)
    disk_cache.write_manifest(ctx, pages, ctx.all_imports, root=tmp_path)
    manifest_path = web / disk_cache._MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text())
    _stale_dep(manifest, pages[1].route, str(tmp_path / "view.py"))
    manifest_path.write_text(json.dumps(manifest))
    _drop_dynamic_states(*markers)
    prepare()
    monkeypatch.setattr(disk_cache, "_predict_dynamic_names", predict)
    try:
        result = disk_cache.try_incremental_rebuild(
            app, compiler_plugins=[], prerender_routes=False, root=tmp_path
        )
    finally:
        _drop_dynamic_states(*markers)
    refreshed = json.loads(manifest_path.read_text())
    return (
        result,
        list(second_states),
        list(refreshed["pages"][pages[1].route]["state_slice"]["schema"]),
    )


def _drop_dynamic_states(*markers: str) -> None:
    """Unregister dynamic-module states whose names contain a marker.

    Args:
        markers: Class name parts, as in the ``reflex.istate.dynamic`` names.
    """
    import reflex.istate.dynamic as istate_dynamic

    for name, cls in list(RegistrationContext.ensure_context().base_states.items()):
        if any(to_snake_case(marker) in name for marker in markers):
            _unregister_state(cls)
    for name in [n for n in vars(istate_dynamic) if any(m in n for m in markers)]:
        delattr(istate_dynamic, name)


def _rebuild_second_collide_page(
    tmp_path,
    monkeypatch,
    *,
    predict: bool,
    two_extra: bool = False,
    two_unique: bool = False,
) -> tuple[Any, list[str], list[str]]:
    """Compile two pages defining a same-named local state, then rebuild the second.

    Args:
        tmp_path: The project root.
        monkeypatch: The pytest monkeypatch fixture.
        predict: Whether the rebuild predicts dynamic state names.
        two_extra: Whether the edited second page defines one more such state.
        two_unique: Whether the edited second page defines a state no other
            page names the same way.

    Returns:
        The rebuild result, the second page's states before the edit, and its
        recorded states after the rebuild.
    """

    def prepare() -> None:
        monkeypatch.setitem(_COLLIDE, "one", 0)
        monkeypatch.setitem(_COLLIDE, "two", 0)
        monkeypatch.setitem(_COLLIDE, "two_extra", two_extra)
        monkeypatch.setitem(_COLLIDE, "two_unique", two_unique)

    result, before, after = _rebuild_second_page(
        tmp_path,
        monkeypatch,
        _page_collide_one,
        _page_collide_two,
        predict=predict,
        markers=("CollideState", "UniqueToTwoState"),
        prepare=prepare,
    )
    assert before[0].endswith("collide_state_0")
    return result, before, after


def test_incremental_rebuild_keeps_colliding_local_state_names(tmp_path, monkeypatch):
    """A page whose local state took a collision suffix keeps it when it misses.

    Local states are named in evaluation order, and the backend evaluates every
    stateful page, so the second page's state stays ``CollideState_0`` there.
    Without prediction every page defining such states is re-evaluated.
    """
    result, before, after = _rebuild_second_collide_page(
        tmp_path, monkeypatch, predict=False
    )
    assert result is True
    assert after == before
    assert (_COLLIDE["one"], _COLLIDE["two"]) == (1, 1)


def test_predicted_local_state_names_rebuild_only_the_changed_page(
    tmp_path, monkeypatch
):
    """With prediction, a verified rebuild evaluates only the changed page."""
    result, before, after = _rebuild_second_collide_page(
        tmp_path, monkeypatch, predict=True
    )
    assert result is True
    assert after == before
    assert (_COLLIDE["one"], _COLLIDE["two"]) == (0, 1)


def test_prediction_accepts_a_new_state_name_no_other_page_uses(tmp_path, monkeypatch):
    """A new local state in a name family of its own cannot shift other pages."""
    result, before, after = _rebuild_second_collide_page(
        tmp_path, monkeypatch, predict=True, two_unique=True
    )
    assert result is True
    assert after[: len(before)] == before
    assert after[-1].endswith("unique_to_two_state")
    assert (_COLLIDE["one"], _COLLIDE["two"]) == (0, 1)


def test_unverified_local_state_prediction_asks_for_a_fresh_compile(
    tmp_path, monkeypatch
):
    """A page that claims different names than recorded fails the prediction.

    The caller then compiles again in a fresh process without prediction.
    """
    with pytest.raises(disk_cache.DynamicStatePredictionError):
        _rebuild_second_collide_page(
            tmp_path, monkeypatch, predict=True, two_extra=True
        )


class SharedCounter(rx.ComponentState):
    """A ``ComponentState`` both counter pages create."""

    value: int = 0

    @classmethod
    def get_component(cls, *children, **props) -> Component:
        """Render the instance's value.

        Args:
            children: Unused.
            props: Unused.

        Returns:
            The component.
        """
        return rx.el.p(cls.value)


_COUNTER = {"one": 0, "two": 0}


def _page_counter_one() -> Component:
    _COUNTER["one"] += 1
    return rx.el.div(SharedCounter.create(), _footer())


def _page_counter_two() -> Component:
    _COUNTER["two"] += 1
    return rx.el.div(SharedCounter.create(), _footer())


def test_predicted_component_state_numbers_rebuild_only_the_changed_page(
    tmp_path, monkeypatch
):
    """A re-evaluated page draws the ``ComponentState`` number of a full compile.

    Instance numbers are handed out in page order. A fresh import starts the
    counter at zero, so the rebuild advances it past the number the first page
    drew instead of evaluating that page again.
    """
    monkeypatch.setattr(SharedCounter, "_per_component_state_instance_count", 0)

    def prepare() -> None:
        monkeypatch.setattr(SharedCounter, "_per_component_state_instance_count", 0)
        monkeypatch.setitem(_COUNTER, "one", 0)
        monkeypatch.setitem(_COUNTER, "two", 0)

    result, before, after = _rebuild_second_page(
        tmp_path,
        monkeypatch,
        _page_counter_one,
        _page_counter_two,
        predict=True,
        markers=("SharedCounter_n",),
        prepare=prepare,
    )
    assert result is True
    assert before[0].endswith("shared_counter_n2")
    assert after == before
    assert (_COUNTER["one"], _COUNTER["two"]) == (0, 1)


def _route_set_rebuild(tmp_path, monkeypatch, edit) -> tuple[Any, Any, Path]:
    """Fully compile two pages, then rebuild after ``edit`` changes the app.

    Args:
        tmp_path: The project root.
        monkeypatch: The pytest monkeypatch fixture.
        edit: Changes the app's page registrations.

    Returns:
        The rebuild result, the app and the web directory.
    """
    web = _use_tmp_web_dir(tmp_path, monkeypatch)
    app = rx.App()
    app.add_page(_page_a, route="/a")
    app.add_page(_page_c, route="/c")
    pages = list(app._unevaluated_pages.values())
    ctx = _compile(pages, app=app)
    _stub_externals(app, monkeypatch)
    for page_ctx in ctx.compiled_pages.values():
        assert page_ctx.output_path is not None
        Path(page_ctx.output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(page_ctx.output_path).write_text(page_ctx.output_code or "")
    disk_cache.write_manifest(ctx, pages, ctx.all_imports, root=tmp_path)
    edit(app)
    evaluated: list[str] = []
    original = disk_cache.CompileContext.compile

    def recording_compile(self, *args, **kwargs):
        evaluated.extend(page.route for page in self.pages)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(disk_cache.CompileContext, "compile", recording_compile)
    result = disk_cache.try_incremental_rebuild(
        app, compiler_plugins=[], prerender_routes=False, root=tmp_path
    )
    return result, evaluated, web


def _add_b(app) -> None:
    app.add_page(_page_b, route="/b")


def _remove_c(app) -> None:
    del app._unevaluated_pages["c"]


def _reorder(app) -> None:
    app._unevaluated_pages = dict(reversed(app._unevaluated_pages.items()))


def _retitle_c(app) -> None:
    import dataclasses

    app._unevaluated_pages["c"] = dataclasses.replace(
        app._unevaluated_pages["c"], title="Renamed"
    )


@pytest.mark.parametrize(
    ("edit", "reason"),
    [
        (_add_b, "added b"),
        (_remove_c, "removed c"),
        (_reorder, "order changed"),
        (_retitle_c, "registered differently"),
    ],
)
def test_page_registry_change_falls_back(tmp_path, monkeypatch, caplog, edit, reason):
    """The page registry is an input of every page (a sidebar lists them).

    Adding, removing, reordering or re-registering a page (its title, say)
    therefore re-evaluates every page, which a full compile does.
    """
    from reflex.compiler import utils as compiler_utils

    with caplog.at_level("INFO", logger=disk_cache.logger.name):
        result, evaluated, web = _route_set_rebuild(tmp_path, monkeypatch, edit)
    assert result is False
    assert evaluated == []
    assert reason in caplog.text
    # Nothing was written or removed: the full compile does that.
    assert Path(compiler_utils.get_page_path("a")).exists()
    assert Path(compiler_utils.get_page_path("c")).exists()
    manifest = json.loads((web / disk_cache._MANIFEST_FILE).read_text())
    assert list(manifest["pages"]) == ["a", "c"]


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

    # Simulate an edit to this module (which defines the user memo): record an
    # unmatchable entry for its file, which both the page's dep set (so the
    # importing page misses) and the stored memo record's closure (so the memo
    # file is dirty) resolve through the shared file table.
    module_file = str(Path(__file__).resolve())
    manifest_path = web / disk_cache._MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text())
    memo_path = disk_cache._memo_output_path(__name__)
    assert memo_path is not None
    assert module_file in manifest["memo_files"][memo_path]["deps"]
    _stale_dep(manifest, memo_route, module_file)
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


def test_new_memo_module_is_emitted_on_first_use(
    tmp_path, monkeypatch, preserve_memo_registries
):
    """A user memo module the previous compile never saw must be emitted.

    Mirrors the review repro: a page starts importing a ``@rx.memo`` from a
    brand-new module. The page misses (its importer changed), but the memo's
    module file is absent from every recorded dependency set — no
    changed-file reasoning can select it — while the recompiled page imports
    the memo's mirrored file, which must therefore be written.
    """
    from reflex_base.components.memo import MEMOS, MemoComponentDefinition

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

    # Rewrite the manifest as if the previous compile never saw the memo's
    # module: the page's recorded deps name only an unrelated changed file
    # (so it misses), and no recorded memo state mentions the module.
    manifest_path = web / disk_cache._MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text())
    _stale_dep(manifest, memo_route, str(tmp_path / "app.py"))
    manifest["memo_files"] = {}
    manifest_path.write_text(json.dumps(manifest))

    assert (
        disk_cache.try_incremental_rebuild(
            app, compiler_plugins=[], prerender_routes=False, root=tmp_path
        )
        is True
    )

    badge_def = next(m for m in MEMOS.values() if m.source_module == __name__)
    assert isinstance(badge_def, MemoComponentDefinition)
    memo_files, _ = compiler.compile_memo_components([badge_def])
    assert memo_files
    for mpath, _mcode in memo_files:
        out_path = compiler_utils.resolve_path_of_web_dir(mpath)
        assert out_path.exists(), "new memo module file was never written"
        assert badge_def.export_name in out_path.read_text(encoding="utf-8")


def test_route_owned_memo_entry_carried_while_owner_hits(
    tmp_path, monkeypatch, preserve_memo_registries
):
    """A route-owned memo entry survives rebuilds while its owner page hits.

    The pre-evaluation registry can't see memos from modules imported inside
    a page function; the entry's owner attribution keeps its on-disk file and
    manifest record intact without re-evaluating anything.
    """
    web = _use_tmp_web_dir(tmp_path, monkeypatch)

    app = rx.App()
    app.add_page(_page_a, route="/a")
    pages = list(app._unevaluated_pages.values())
    owner_route = pages[0].route
    ctx = _compile(pages)
    disk_cache.write_manifest(ctx, pages, ctx.all_imports, root=tmp_path)
    _stub_externals(app, monkeypatch)

    lazy_file = web / "app_components" / "lazy_module.jsx"
    lazy_file.parent.mkdir(parents=True, exist_ok=True)
    lazy_file.write_text("export const Lazy = () => null;")
    manifest_path = web / disk_cache._MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text())
    manifest["memo_files"][str(lazy_file)] = {
        "def_keys": [["Lazy", "lazy_module"]],
        "deps": [],
        "owner_route": owner_route,
    }
    manifest_path.write_text(json.dumps(manifest))

    assert (
        disk_cache.try_incremental_rebuild(
            app, compiler_plugins=[], prerender_routes=False, root=tmp_path
        )
        is True
    )

    assert lazy_file.read_text() == "export const Lazy = () => null;"
    # The all-hit rebuild left the manifest record (including the entry) intact.
    written = json.loads(manifest_path.read_text())
    assert written["memo_files"][str(lazy_file)]["owner_route"] == owner_route


def test_new_lazy_memo_module_is_emitted_on_first_use(
    tmp_path, monkeypatch, preserve_memo_registries
):
    """A new memo module imported inside a page function must be emitted.

    The pre-evaluation registry cannot see this module, and the changed-file
    net cannot see a new file. The post-evaluation pass over the recompiled
    routes' owned memos must demand its output file.
    """
    import importlib

    module_name = "lazy_memo_mod_t1"
    (tmp_path / f"{module_name}.py").write_text(
        "import reflex as rx\n"
        "\n"
        "@rx.memo\n"
        "def lazy_badge(text: str) -> rx.Component:\n"
        "    return rx.el.span(text)\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    def _page_lazy() -> Component:
        mod = importlib.import_module(module_name)
        return rx.el.div(mod.lazy_badge(text="hi"))

    web = _use_tmp_web_dir(tmp_path, monkeypatch)
    app = rx.App()
    app.add_page(_page_lazy, route="/lazy")
    pages = list(app._unevaluated_pages.values())
    lazy_route = pages[0].route
    try:
        ctx = _compile(pages)
        disk_cache.write_manifest(ctx, pages, ctx.all_imports, root=tmp_path)
        _stub_externals(app, monkeypatch)

        manifest_path = web / disk_cache._MANIFEST_FILE
        manifest = json.loads(manifest_path.read_text())
        lazy_path = disk_cache._memo_output_path(module_name)
        assert lazy_path is not None
        # Sanity: the full compile recorded the entry as owned by the page.
        assert manifest["memo_files"][lazy_path]["owner_route"] == lazy_route

        # Surgery: the previous compile never saw the lazy module, and the
        # page misses via an unrelated changed file.
        del manifest["memo_files"][lazy_path]
        _stale_dep(manifest, lazy_route, str(tmp_path / "app.py"))
        manifest_path.write_text(json.dumps(manifest))

        assert (
            disk_cache.try_incremental_rebuild(
                app, compiler_plugins=[], prerender_routes=False, root=tmp_path
            )
            is True
        )

        from reflex_base.components.memo import MEMOS, MemoComponentDefinition

        lazy_def = next(m for m in MEMOS.values() if m.source_module == module_name)
        assert isinstance(lazy_def, MemoComponentDefinition)
        out_path = Path(lazy_path)
        assert out_path.exists(), "lazy memo module file was never written"
        assert lazy_def.export_name in out_path.read_text(encoding="utf-8")
        # The refreshed manifest re-records the entry with its owner.
        written = json.loads(manifest_path.read_text())
        assert written["memo_files"][lazy_path]["owner_route"] == lazy_route
    finally:
        sys.modules.pop(module_name, None)


class _MemoCacheState(rx.State):
    value: str = "x"
    other: str = "y"


_SHARED_MEMO = {"edit_one": False}


def _page_shared_one() -> Component:
    if _SHARED_MEMO["edit_one"]:
        return rx.el.div(rx.el.p(_MemoCacheState.other, class_name="one"))
    return rx.el.div(rx.el.p(_MemoCacheState.value, class_name="shared"))


def _page_shared_two() -> Component:
    return rx.el.div(rx.el.p(_MemoCacheState.value, class_name="shared"))


def _memo_file_of(page_ctx: PageContext) -> Path:
    """The single auto memo file a test page's output imports.

    Args:
        page_ctx: The compiled page.

    Returns:
        The memo file path.
    """
    [(tag, _)] = page_ctx.memo_uses
    return Path(disk_cache._memo_file(tag))


def test_incremental_miss_leaves_the_memo_a_reused_page_shares(
    tmp_path, monkeypatch, preserve_memo_registries
):
    """A miss never touches the memo files of the pages it reuses.

    Pages one and two render the same stateful subtree, so both import the
    same content-addressed auto memo. Editing page one gives it another
    memo; the shared memo must survive for page two, which still imports it.
    """
    from reflex.compiler import compiler
    from reflex.compiler import utils as compiler_utils

    web = _use_tmp_web_dir(tmp_path, monkeypatch)
    app = rx.App()
    app.add_page(_page_shared_one, route="/one")
    app.add_page(_page_shared_two, route="/two")
    pages = list(app._unevaluated_pages.values())
    route_one, route_two = pages[0].route, pages[1].route
    ctx = _compile(pages)
    one_ctx, two_ctx = ctx.compiled_pages[route_one], ctx.compiled_pages[route_two]
    shared = _memo_file_of(one_ctx)
    assert shared == _memo_file_of(two_ctx), "both pages must share the memo"
    # The full compile's on-disk memo state.
    memo_files, _ = compiler.compile_memo_components(ctx.auto_memo_components.values())
    assert [Path(path) for path, _ in memo_files] == [shared]
    for mpath, mcode in memo_files:
        compiler_utils.write_file(compiler_utils.resolve_path_of_web_dir(mpath), mcode)
    compiler_utils.prune_stale_memo_files(path for path, _ in memo_files)
    disk_cache.write_manifest(ctx, pages, ctx.all_imports, root=tmp_path)
    _stub_externals(app, monkeypatch)
    manifest_path = web / disk_cache._MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text())
    [tag] = manifest["pages"][route_two]["memo_keys"]
    assert manifest["pages"][route_one]["memo_keys"] == [tag]
    assert manifest["app_root"]["memo_keys"] == []

    # Edit page one so it renders another subtree, and make only it miss.
    monkeypatch.setitem(_SHARED_MEMO, "edit_one", True)
    _stale_dep(manifest, route_one, str(tmp_path / "data.md"))
    manifest_path.write_text(json.dumps(manifest))
    assert (
        disk_cache.try_incremental_rebuild(
            app, compiler_plugins=[], prerender_routes=False, root=tmp_path
        )
        is True
    )

    # The shared memo is still there for page two; page one got a new one.
    assert shared.exists()
    refreshed = json.loads(manifest_path.read_text())
    [new_tag] = refreshed["pages"][route_one]["memo_keys"]
    assert new_tag != tag
    assert refreshed["pages"][route_two]["memo_keys"] == [tag]
    new_file = Path(disk_cache._memo_file(new_tag))
    assert new_file.exists()
    page_one = Path(compiler_utils.get_page_path(route_one)).read_text()
    assert new_tag in page_one
    assert tag not in page_one
    memo_manifest = compiler_utils._read_memo_manifest(web)
    assert memo_manifest == {
        str(path.relative_to(web)).replace(os.sep, "/") for path in (shared, new_file)
    }


def test_incremental_miss_drops_the_memo_no_page_uses(
    tmp_path, monkeypatch, preserve_memo_registries
):
    """A memo only the recompiled page used is deleted once it stops using it."""
    from reflex.compiler import compiler
    from reflex.compiler import utils as compiler_utils

    web = _use_tmp_web_dir(tmp_path, monkeypatch)
    app = rx.App()
    app.add_page(_page_shared_one, route="/one")
    pages = list(app._unevaluated_pages.values())
    route_one = pages[0].route
    ctx = _compile(pages)
    old_file = _memo_file_of(ctx.compiled_pages[route_one])
    memo_files, _ = compiler.compile_memo_components(ctx.auto_memo_components.values())
    for mpath, mcode in memo_files:
        compiler_utils.write_file(compiler_utils.resolve_path_of_web_dir(mpath), mcode)
    compiler_utils.prune_stale_memo_files(path for path, _ in memo_files)
    disk_cache.write_manifest(ctx, pages, ctx.all_imports, root=tmp_path)
    _stub_externals(app, monkeypatch)
    manifest_path = web / disk_cache._MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text())
    monkeypatch.setitem(_SHARED_MEMO, "edit_one", True)
    _stale_dep(manifest, route_one, str(tmp_path / "data.md"))
    manifest_path.write_text(json.dumps(manifest))
    assert (
        disk_cache.try_incremental_rebuild(
            app, compiler_plugins=[], prerender_routes=False, root=tmp_path
        )
        is True
    )
    assert not old_file.exists()
    refreshed = json.loads(manifest_path.read_text())
    [new_tag] = refreshed["pages"][route_one]["memo_keys"]
    new_relative = str(Path(disk_cache._memo_file(new_tag)).relative_to(web)).replace(
        os.sep, "/"
    )
    assert compiler_utils._read_memo_manifest(web) == {new_relative}


def test_incremental_miss_keeps_the_memo_the_app_root_shares(
    tmp_path, monkeypatch, preserve_memo_registries
):
    """A memo the app root also imports survives the page dropping it."""
    from reflex.compiler import compiler
    from reflex.compiler import utils as compiler_utils

    web = _use_tmp_web_dir(tmp_path, monkeypatch)
    app = rx.App()
    app.add_page(_page_shared_one, route="/one")
    pages = list(app._unevaluated_pages.values())
    route_one = pages[0].route
    ctx = _compile(pages)
    shared = _memo_file_of(ctx.compiled_pages[route_one])
    # An app wrap rendering the same stateful subtree imports the same memo.
    compiler._memoize_stateful_app_wraps(
        rx.fragment(rx.el.p(_MemoCacheState.value, class_name="shared")), ctx
    )
    memo_files, _ = compiler.compile_memo_components(ctx.auto_memo_components.values())
    assert [Path(path) for path, _ in memo_files] == [shared]
    for mpath, mcode in memo_files:
        compiler_utils.write_file(compiler_utils.resolve_path_of_web_dir(mpath), mcode)
    compiler_utils.prune_stale_memo_files(path for path, _ in memo_files)
    disk_cache.write_manifest(ctx, pages, ctx.all_imports, root=tmp_path)
    _stub_externals(app, monkeypatch)
    manifest_path = web / disk_cache._MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text())
    assert (
        manifest["app_root"]["memo_keys"] == manifest["pages"][route_one]["memo_keys"]
    )
    monkeypatch.setitem(_SHARED_MEMO, "edit_one", True)
    _stale_dep(manifest, route_one, str(tmp_path / "data.md"))
    manifest_path.write_text(json.dumps(manifest))
    assert (
        disk_cache.try_incremental_rebuild(
            app, compiler_plugins=[], prerender_routes=False, root=tmp_path
        )
        is True
    )
    assert shared.exists()


def _page_radix() -> Component:
    return rx.el.div(rx.button("Radix"), _footer())


def _page_memoized_radix() -> Component:
    return rx.el.div(
        rx.text("x", color=_MemoCacheState.value, on_click=rx.console_log("c"))
    )


def test_memoized_radix_component_is_recorded_as_radix(tmp_path, monkeypatch):
    """A Radix component auto-memoization moved out of the page tree counts."""
    from reflex_components_radix.plugin import RadixThemesPlugin

    web = _use_tmp_web_dir(tmp_path, monkeypatch)
    app = rx.App()
    app.add_page(_page_memoized_radix, route="/m")
    pages = list(app._unevaluated_pages.values())
    ctx = _compile(pages, plugins=[RadixThemesPlugin.create_implicit()])
    page_ctx = ctx.compiled_pages[pages[0].route]
    assert page_ctx.memo_uses, "the Radix text must be auto-memoized"
    disk_cache.write_manifest(ctx, pages, ctx.all_imports, root=tmp_path)
    manifest = json.loads((web / disk_cache._MANIFEST_FILE).read_text())
    assert manifest["pages"][pages[0].route]["radix"] is True


def test_reused_radix_page_keeps_the_implicit_plugin_enabled(tmp_path, monkeypatch):
    """A rebuild that compiles no Radix page still ships the Radix stylesheet.

    The implicit plugin enables itself while compiling a Radix component; a
    page reused from disk is not compiled, so the manifest records the page's
    Radix use and the rebuild enables the plugin from it.
    """
    from reflex_components_radix.plugin import RadixThemesPlugin

    web = _use_tmp_web_dir(tmp_path, monkeypatch)
    app = rx.App()
    app.add_page(_page_radix, route="/radix")
    app.add_page(_page_a, route="/a")
    pages = list(app._unevaluated_pages.values())
    ctx = _compile(pages, plugins=[RadixThemesPlugin.create_implicit()])
    _stub_externals(app, monkeypatch)
    disk_cache.write_manifest(ctx, pages, ctx.all_imports, root=tmp_path)
    manifest_path = web / disk_cache._MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text())
    assert manifest["pages"][pages[0].route]["radix"] is True
    assert manifest["pages"][pages[1].route]["radix"] is False

    # An all-hit rebuild, and one that recompiles only the plain page.
    for stale in (None, pages[1].route):
        if stale is not None:
            _stale_dep(manifest, stale, str(tmp_path / "view.py"))
            manifest_path.write_text(json.dumps(manifest))
        plugin = RadixThemesPlugin.create_implicit()
        assert not plugin.enabled
        assert (
            disk_cache.try_incremental_rebuild(
                app, compiler_plugins=[plugin], prerender_routes=False, root=tmp_path
            )
            is True
        )
        assert plugin.enabled
        assert plugin.get_stylesheet_paths()


def test_recompiled_page_leaves_a_hit_pages_state_to_it(tmp_path, monkeypatch):
    """A state a hit page recorded is not claimed by a recompiled page.

    In a process that evaluates only the recompiled pages, one of them can
    be the first to import the module defining a state another page owns.
    """
    miss_ctx = SimpleNamespace(
        stateful_routes={
            "/miss": ["app.shared", "app.own"],
            "/other": ["app.shared"],
        }
    )
    manifest = _manifest({
        "/hit": {"state_slice": {"schema": {"app.shared": []}}},
        "/miss": {"state_slice": None},
        "/other": {"state_slice": None},
    })
    disk_cache._disown_hit_page_states(
        cast(Any, miss_ctx), manifest, {"/miss", "/other"}
    )
    assert miss_ctx.stateful_routes == {"/miss": ["app.own"]}


def test_load_manifest_rejects_wrong_schema(tmp_path, monkeypatch):
    web = _use_tmp_web_dir(tmp_path, monkeypatch)
    (web / disk_cache._MANIFEST_FILE).write_text(json.dumps({"schema": 999}))
    assert disk_cache.load_manifest() is None


def test_update_manifest_for_misses_keeps_complete_imports(tmp_path, monkeypatch):
    web = _use_tmp_web_dir(tmp_path, monkeypatch)
    monkeypatch.setattr(
        page_cache, "state_dependency_index", lambda root=None: ({}, set())
    )
    monkeypatch.setattr(page_cache, "page_dependency_entries", lambda *a, **k: [])

    page = _FakePage(route="/a", component=_page_a)
    page_ctx = SimpleNamespace(
        root_component=rx.el.div(),
        app_wrap_components={},
        frontend_imports={},
        memo_uses={},
    )
    miss_ctx = SimpleNamespace(compiled_pages={"/a": page_ctx}, stateful_routes={})
    complete_imports = {"memo-lib": [ImportVar("MemoThing")]}
    manifest = _manifest({"/a": {"deps": [], "app_wraps": {}, "is_stateful": False}})

    assert disk_cache._update_manifest_for_misses(
        manifest,
        cast(Any, miss_ctx),
        [page],
        complete_imports,
        root=tmp_path,
        memo_state={},
        memo_file_entries={},
        registrations={"/a": "recorded"},
        module_states=manifest["module_states"],
    )
    disk_cache._write(manifest)

    written = json.loads((web / disk_cache._MANIFEST_FILE).read_text())
    assert disk_cache._deserialize_imports(written["all_imports"]) == complete_imports


def test_update_manifest_refreshes_imports_without_misses(tmp_path, monkeypatch):
    """A memo-only rewrite that adds a package must reach the manifest."""
    web = _use_tmp_web_dir(tmp_path, monkeypatch)
    manifest = _manifest({}, all_imports={"old-lib": [{"tag": "Old"}]})
    memo_imports = {"old-lib": [ImportVar("Old")], "memo-lib": [ImportVar("Memo")]}

    assert disk_cache._update_manifest_for_misses(
        manifest,
        None,
        [],
        memo_imports,
        root=tmp_path,
        memo_state={},
        memo_file_entries={},
        registrations={"/a": "recorded"},
        module_states=manifest["module_states"],
    )
    disk_cache._write(manifest)

    written = json.loads((web / disk_cache._MANIFEST_FILE).read_text())
    assert disk_cache._deserialize_imports(written["all_imports"]) == memo_imports
    # Nothing changed: nothing to write.
    assert not disk_cache._update_manifest_for_misses(
        written,
        None,
        [],
        memo_imports,
        root=tmp_path,
        memo_state={},
        memo_file_entries={},
        registrations={"/a": "recorded"},
        module_states=written["module_states"],
    )


def _page_loop_a() -> Component:
    return rx.el.ul(rx.foreach(["a", "b"], lambda item: rx.el.li(item)))


def _page_loop_b() -> Component:
    return rx.el.ul(rx.foreach(["c", "d"], lambda item: rx.el.li(item)))


def _page_loop_c() -> Component:
    return rx.el.ul(rx.foreach(["e", "f"], lambda item: rx.el.li(item)))


def test_generated_names_do_not_depend_on_other_pages():
    """A page compiled alone gets the same generated names as in a full compile.

    ``rx.foreach`` draws its loop variable from the unique-name generator. If
    that sequence were process-wide, an incremental compile of one page would
    hand it the names the cached pages already use.
    """
    full = _compile([
        _FakePage(route="/la", component=_page_loop_a),
        _FakePage(route="/lb", component=_page_loop_b),
        _FakePage(route="/lc", component=_page_loop_c),
    ])
    alone = _compile([_FakePage(route="/lc", component=_page_loop_c)])
    assert (
        full.compiled_pages["/lc"].output_code
        == alone.compiled_pages["/lc"].output_code
    )
    # Different pages still draw different names.
    la, lb = full.compiled_pages["/la"], full.compiled_pages["/lb"]
    assert la.output_code is not None
    assert lb.output_code is not None
    assert la.output_code != lb.output_code


_TWO_PAGE_MODULE = """\
import reflex as rx

CALLS = {"a": 0, "b": 0}


def page_a():
    CALLS["a"] += 1
    return rx.el.p("a")


def page_b():
    CALLS["b"] += 1
    return rx.el.p("b")
"""


@pytest.mark.parametrize("hinted", [True, False])
def test_incremental_rebuild_recompiles_only_the_edited_function(
    tmp_path, monkeypatch, hinted
):
    """Editing one page function recompiles only that page of its module.

    The watcher reports the module file; a page tracking its function's slice
    of that file must still be validated.
    """
    import importlib

    module_name = "two_page_module_t7"
    module = tmp_path / f"{module_name}.py"
    module.write_text(_TWO_PAGE_MODULE)
    monkeypatch.syspath_prepend(str(tmp_path))
    web = _use_tmp_web_dir(tmp_path, monkeypatch)
    try:
        mod = importlib.import_module(module_name)
        app = rx.App()
        app.add_page(mod.page_a, route="/a")
        app.add_page(mod.page_b, route="/b")
        pages = list(app._unevaluated_pages.values())
        ctx = _compile(pages, app=app)
        disk_cache.write_manifest(ctx, pages, ctx.all_imports, root=tmp_path)
        _stub_externals(app, monkeypatch)
        manifest = json.loads((web / disk_cache._MANIFEST_FILE).read_text())
        assert disk_cache.manifest_dependency_files(manifest) >= {str(module.resolve())}

        module.write_text(_TWO_PAGE_MODULE.replace('rx.el.p("a")', 'rx.el.p("a2")'))
        mod.CALLS.update(a=0, b=0)
        disk_cache.set_changed_hint({module} if hinted else None)
        result = disk_cache.try_incremental_rebuild(
            app, compiler_plugins=[], prerender_routes=False, root=tmp_path
        )
    finally:
        disk_cache.set_changed_hint(None)
        sys.modules.pop(module_name, None)
    assert result is True
    assert mod.CALLS == {"a": 1, "b": 0}


def _labelled(label: str) -> Component:
    return rx.el.p(label)


def test_registration_digest_tracks_partial_arguments():
    """A page bound with ``functools.partial`` changes with its arguments."""
    import functools

    def digest(label: str) -> str:
        page = _FakePage(route="/p", component=functools.partial(_labelled, label))
        return disk_cache.registration_digests([page])["/p"]

    assert digest("old") == digest("old")
    assert digest("old") != digest("new")


def test_partial_page_depends_on_its_function_module(tmp_path, monkeypatch):
    """A ``functools.partial`` page depends on its wrapped function's file."""
    import functools
    import importlib

    module = tmp_path / "partial_view_module.py"
    module.write_text("def view(label):\n    return label\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    try:
        view = importlib.import_module("partial_view_module").view
        files = page_cache._component_source_files(
            functools.partial(view, "x"), tmp_path.resolve()
        )
    finally:
        sys.modules.pop("partial_view_module", None)
    assert files == {str(module.resolve())}


@pytest.mark.parametrize("predict", [False, True])
def test_expand_miss_pages_keeps_page_order(monkeypatch, predict):
    """Re-evaluated pages are evaluated in page order, whatever added them.

    ``ComponentState`` numbers and memo emit order follow evaluation order.
    """
    pages = [_FakePage(f"/{name}", _page_a) for name in "abcd"]

    def entry(claims: list[list[str]]) -> dict[str, Any]:
        return {"dynamic_claims": claims}

    manifest = {
        "pages": {
            "/a": entry([]),
            "/b": entry([["LocalState", "LocalState"]]),
            "/c": entry([]),
            "/d": entry([]),
        }
    }
    monkeypatch.setattr(disk_cache, "_predict_dynamic_names", predict)
    misses = disk_cache._expand_miss_pages([pages[3]], pages, manifest, {"/a"})
    expected = ["/a", "/d"] if predict else ["/a", "/b", "/d"]
    assert [page.route for page in misses] == expected


@pytest.mark.parametrize("predict", [False, True])
def test_reordering_pages_falls_back_before_evaluating(tmp_path, monkeypatch, predict):
    """A reorder changes the page registry, which every page may read."""
    web = _use_tmp_web_dir(tmp_path, monkeypatch)
    app = rx.App()
    app.add_page(_page_collide_one, route="/one")
    app.add_page(_page_collide_two, route="/two")
    pages = list(app._unevaluated_pages.values())
    ctx = _compile(pages, app=app)
    _stub_externals(app, monkeypatch)
    disk_cache.write_manifest(ctx, pages, ctx.all_imports, root=tmp_path)
    assert (web / disk_cache._MANIFEST_FILE).exists()
    monkeypatch.setattr(
        app, "_unevaluated_pages", dict(reversed(app._unevaluated_pages.items()))
    )
    _drop_dynamic_states("CollideState")
    monkeypatch.setitem(_COLLIDE, "one", 0)
    monkeypatch.setitem(_COLLIDE, "two", 0)
    monkeypatch.setattr(disk_cache, "_predict_dynamic_names", predict)
    try:
        result = disk_cache.try_incremental_rebuild(
            app, compiler_plugins=[], prerender_routes=False, root=tmp_path
        )
    finally:
        _drop_dynamic_states("CollideState")
    assert result is False
    assert (_COLLIDE["one"], _COLLIDE["two"]) == (0, 0)


def test_manifest_dependency_files_cover_every_recorded_input():
    """The daemon watches, and checks at startup, every input the manifest records.

    Import-time state files and memo source closures belong to no page, so
    they are listed alongside the page dependencies and global inputs.
    """
    manifest = {
        "pages": {"index": {"deps": ["/app/pages.py::index", "/app/data.md"]}},
        "globals": {"reflex": "0.0.0", "rxconfig": "/app/rxconfig.py"},
        "globals_absent": ["/app/uv.lock"],
        "module_states": {"files": ["/app/state.py"]},
        "memo_files": {"memo.js": {"deps": ["/lib/memo.py"]}},
    }
    assert disk_cache.manifest_dependency_entries(manifest) == {
        "/app/pages.py::index",
        "/app/data.md",
        "/app/rxconfig.py",
        "/app/state.py",
        "/lib/memo.py",
    }
    assert disk_cache.manifest_dependency_files(manifest) == {
        "/app/pages.py",
        "/app/data.md",
        "/app/rxconfig.py",
        "/app/uv.lock",
        "/app/state.py",
        "/lib/memo.py",
    }
