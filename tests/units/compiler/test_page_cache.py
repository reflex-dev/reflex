"""Tests for the per-page dependency graph used by the incremental compile cache."""

import importlib
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

from reflex.compiler import page_cache


def test_class_module_file_respects_each_project_root(tmp_path, monkeypatch):
    """A class excluded in one project can be a dependency in another."""
    module = ModuleType("review_class_roots")
    module.__file__ = str(tmp_path / "component.py")
    monkeypatch.setitem(sys.modules, module.__name__, module)
    cls = type("RootScoped", (), {"__module__": module.__name__})
    assert page_cache._class_module_file(cls, (tmp_path / "other",)) is None
    assert page_cache._class_module_file(cls, (tmp_path,)) == Path(module.__file__)


def test_loaded_modules_reuse_resolution_and_discover_new_modules(
    tmp_path, monkeypatch
):
    """Cache stable module paths without missing imports or changes to roots."""
    source = tmp_path / "cached_module.py"
    source.write_text("VALUE = 1\n")
    module = ModuleType("cached_review_module")
    module.__file__ = str(source)
    monkeypatch.setitem(sys.modules, module.__name__, module)
    original = Path.resolve
    resolutions = []

    def resolve(path, *args, **kwargs):
        """Count resolutions of the test module's source file.

        Returns:
            The resolved path.
        """
        if path == source:
            resolutions.append(path)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve)
    assert str(source) in page_cache._loaded_first_party_modules(tmp_path)
    added = ModuleType("new_review_module")
    added.__file__ = str(tmp_path / "added.py")
    monkeypatch.setitem(sys.modules, added.__name__, added)
    assert added.__file__ in page_cache._loaded_first_party_modules(tmp_path)
    assert len(resolutions) == 1
    assert str(source) not in page_cache._loaded_first_party_modules(tmp_path / "other")


def _prepare_runtime_module(root, monkeypatch, module_name, *, import_root=None):
    """Create a temporary module and make it importable.

    Args:
        root: Directory where the module file is written.
        monkeypatch: Pytest monkeypatch fixture.
        module_name: Name of the module to create.
        import_root: Directory added to ``sys.path``. Defaults to ``root``.

    Returns:
        The created module file path.
    """
    module_file = root / f"{module_name}.py"
    module_file.write_text("VALUE = 1\n")
    monkeypatch.syspath_prepend(str(import_root or root))
    sys.modules.pop(module_name, None)
    importlib.invalidate_caches()
    return module_file


def _forget_modules(*module_names):
    """Remove temporary modules imported by a test."""
    for module_name in module_names:
        sys.modules.pop(module_name, None)


def test_global_epoch_tracks_global_files(tmp_path):
    (tmp_path / "rxconfig.py").write_text("config = 1\n")
    (tmp_path / "other.py").write_text("x = 1\n")
    epoch = page_cache.global_epoch(root=tmp_path)
    # editing a non-global file does NOT change the epoch
    (tmp_path / "other.py").write_text("x = 2\n")
    assert page_cache.global_epoch(root=tmp_path) == epoch
    # editing a genuinely-global file (rxconfig.py) DOES
    (tmp_path / "rxconfig.py").write_text("config = 2\n")
    assert page_cache.global_epoch(root=tmp_path) != epoch


def test_global_epoch_tracks_app_entrypoint(tmp_path, monkeypatch):
    """Editing the app entrypoint (theme/app_wraps live there) bumps the epoch.

    App-wide config is configured where ``rx.App`` is built, not in any page's
    dependency set, so without this an edit to it would leave every page a hit
    and the reused on-disk app root / contexts / theme stale.
    """
    (tmp_path / "rxconfig.py").write_text("config = 1\n")
    entrypoint = (tmp_path / "myapp.py").resolve()
    entrypoint.write_text("app = rx.App(theme=light)\n")
    monkeypatch.setattr(
        page_cache, "_app_entrypoint_file", lambda root=None: entrypoint
    )
    epoch = page_cache.global_epoch(root=tmp_path)
    # editing the app entrypoint DOES change the epoch
    entrypoint.write_text("app = rx.App(theme=dark)\n")
    assert page_cache.global_epoch(root=tmp_path) != epoch


def test_app_entrypoint_file_resolution(tmp_path, monkeypatch):
    import sys
    from types import ModuleType, SimpleNamespace

    monkeypatch.setattr(
        "reflex.config.get_config", lambda: SimpleNamespace(module="fake_entry_mod")
    )
    mod = ModuleType("fake_entry_mod")
    monkeypatch.setitem(sys.modules, "fake_entry_mod", mod)

    # no __file__ on the module -> None
    assert page_cache._app_entrypoint_file(root=tmp_path) is None

    # a file under the project root -> resolved
    entry = tmp_path / "myapp" / "myapp.py"
    entry.parent.mkdir()
    entry.write_text("app = 1\n")
    mod.__file__ = str(entry)
    assert page_cache._app_entrypoint_file(root=tmp_path) == entry.resolve()

    # a file outside the project root -> None (not a project input)
    outside = tmp_path.parent / "elsewhere.py"
    mod.__file__ = str(outside)
    assert page_cache._app_entrypoint_file(root=tmp_path) is None


def test_app_dependency_files_keeps_config_excludes_pages(tmp_path, monkeypatch):
    """The entrypoint's config closure, with page modules as traversal barriers.

    entry imports a config-only ``theme.py`` and a page; the page imports a view
    and (also) theme. The result must keep entry + theme (theme is reached from
    the entrypoint directly, even though a page imports it too) and exclude the
    page module and its view (tracked per page).
    """
    from types import SimpleNamespace

    entry = tmp_path / "myapp.py"
    theme = tmp_path / "theme.py"
    page = tmp_path / "pages" / "index.py"
    view = tmp_path / "components" / "hero.py"
    graph = {
        str(entry): {str(theme), str(page)},
        str(page): {str(view), str(theme)},
        str(theme): set(),
        str(view): set(),
    }
    monkeypatch.setattr(page_cache, "_app_entrypoint_file", lambda root=None: entry)
    monkeypatch.setattr(
        page_cache,
        "_loaded_first_party_modules",
        lambda root: {
            str(entry): "myapp",
            str(theme): "theme",
            str(page): "pages.index",
            str(view): "components.hero",
        },
    )
    monkeypatch.setattr(
        page_cache,
        "_module_import_edges",
        lambda file, modname, file_to_mod: graph[file],
    )
    monkeypatch.setattr(
        page_cache, "_component_source_files", lambda comp, root: {str(page)}
    )

    result = page_cache.app_dependency_files(
        [SimpleNamespace(component=object())], root=tmp_path
    )
    assert result == {str(entry), str(theme)}


def test_global_epoch_excludes_page_modules(tmp_path, monkeypatch):
    """A page-module edit keeps the epoch (incremental); an app-config edit bumps it."""
    from types import SimpleNamespace

    (tmp_path / "rxconfig.py").write_text("c = 1\n")
    entry = tmp_path / "myapp.py"
    entry.write_text("app = 1\n")
    theme = tmp_path / "theme.py"
    theme.write_text("t = 1\n")
    page = tmp_path / "index.py"
    page.write_text("p = 1\n")
    graph = {str(entry): {str(theme), str(page)}, str(page): set(), str(theme): set()}
    monkeypatch.setattr(page_cache, "_app_entrypoint_file", lambda root=None: entry)
    monkeypatch.setattr(
        page_cache,
        "_loaded_first_party_modules",
        lambda root: {
            str(entry): "myapp",
            str(theme): "theme",
            str(page): "index",
        },
    )
    monkeypatch.setattr(
        page_cache,
        "_module_import_edges",
        lambda file, modname, file_to_mod: graph[file],
    )
    monkeypatch.setattr(
        page_cache, "_component_source_files", lambda comp, root: {str(page)}
    )
    pages = [SimpleNamespace(component=object())]

    epoch = page_cache.global_epoch(root=tmp_path, pages=pages)
    # editing a page module does NOT change the epoch (tracked per page instead)
    page.write_text("p = 2\n")
    assert page_cache.global_epoch(root=tmp_path, pages=pages) == epoch
    # editing app-level config the entrypoint imports (theme) DOES
    theme.write_text("t = 2\n")
    assert page_cache.global_epoch(root=tmp_path, pages=pages) != epoch


def test_global_epoch_hashes_only_app_dependency_closure(tmp_path, monkeypatch):
    """Unrelated first-party modules do not make the app epoch coarse."""
    from types import SimpleNamespace

    entry = tmp_path / "myapp.py"
    theme = tmp_path / "theme.py"
    unrelated = tmp_path / "unrelated.py"
    for path, code in (
        (entry, "import theme\n"),
        (theme, "t = 1\n"),
        (unrelated, "x = 1\n"),
    ):
        path.write_text(code)
    graph = {str(entry): {str(theme)}, str(theme): set(), str(unrelated): set()}
    monkeypatch.setattr(page_cache, "_app_entrypoint_file", lambda root=None: entry)
    monkeypatch.setattr(
        page_cache,
        "_loaded_first_party_modules",
        lambda root: {
            str(entry): "myapp",
            str(theme): "theme",
            str(unrelated): "unrelated",
        },
    )
    monkeypatch.setattr(
        page_cache,
        "_module_import_edges",
        lambda file, modname, file_to_mod: graph[file],
    )

    epoch = page_cache.global_epoch(
        root=tmp_path, pages=[SimpleNamespace(component=object())]
    )
    unrelated.write_text("x = 2\n")
    assert (
        page_cache.global_epoch(
            root=tmp_path, pages=[SimpleNamespace(component=object())]
        )
        == epoch
    )
    theme.write_text("t = 2\n")
    assert (
        page_cache.global_epoch(
            root=tmp_path, pages=[SimpleNamespace(component=object())]
        )
        != epoch
    )


def test_app_dependency_files_skips_graph_without_entrypoint(tmp_path, monkeypatch):
    monkeypatch.setattr(page_cache, "_app_entrypoint_file", lambda root=None: None)

    def fail_loaded_first_party_modules(root):
        msg = "module map should not be built without an entrypoint"
        raise AssertionError(msg)

    monkeypatch.setattr(
        page_cache, "_loaded_first_party_modules", fail_loaded_first_party_modules
    )

    assert page_cache.app_dependency_files(root=tmp_path) == set()


def test_app_dependency_files_tracks_dynamic_import_config_read(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from reflex.utils import prerequisites

    entry = tmp_path / "myapp.py"
    dynamic = tmp_path / "dynamic_theme.py"
    config_file = tmp_path / "theme.json"
    entry.write_text(
        "import importlib\ntheme = importlib.import_module('dynamic_theme').THEME\n"
    )
    dynamic.write_text(
        "from pathlib import Path\nTHEME = Path('theme.json').read_text()\n"
    )
    config_file.write_text('"light"\n')
    config = SimpleNamespace(
        module="myapp",
        app_module=None,
        _app_name_is_valid=True,
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv("REFLEX_COMPILE_CACHE", "1")
    monkeypatch.setattr(prerequisites, "get_config", lambda: config)
    monkeypatch.setattr("reflex.config.get_config", lambda: config)
    _forget_modules("myapp", "dynamic_theme")

    try:
        prerequisites.get_app()
        deps = page_cache.app_dependency_files(root=tmp_path)
        epoch = page_cache.global_epoch(root=tmp_path)

        config_file.write_text('"dark"\n')
    finally:
        _forget_modules("myapp", "dynamic_theme")

    assert str(dynamic.resolve()) in deps
    assert str(config_file.resolve()) in deps
    assert page_cache.global_epoch(root=tmp_path) != epoch


def test_app_dependency_files_subtracts_pages_from_app_import_reads(
    tmp_path, monkeypatch
):
    from types import SimpleNamespace

    from reflex.utils import prerequisites

    entry = tmp_path / "myapp.py"
    theme = tmp_path / "theme.py"
    page = tmp_path / "page.py"
    view = tmp_path / "view.py"
    entry.write_text("import theme\nfrom page import index\napp_theme = theme.THEME\n")
    theme.write_text("THEME = 'light'\n")
    page.write_text("from view import render\n\ndef index():\n    return render()\n")
    view.write_text("def render():\n    return 'view'\n")
    config = SimpleNamespace(
        module="myapp",
        app_module=None,
        _app_name_is_valid=True,
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv("REFLEX_COMPILE_CACHE", "1")
    monkeypatch.setattr(prerequisites, "get_config", lambda: config)
    monkeypatch.setattr("reflex.config.get_config", lambda: config)
    _forget_modules("myapp", "theme", "page", "view")

    try:
        prerequisites.get_app()
        pages = [SimpleNamespace(component=sys.modules["page"].index)]
        deps = page_cache.app_dependency_files(pages, root=tmp_path)
    finally:
        _forget_modules("myapp", "theme", "page", "view")

    assert deps == {str(entry.resolve()), str(theme.resolve())}


def test_record_reads_tracks_executed_importlib_import(tmp_path, monkeypatch):
    module_name = "runtime_import_dep_for_page_cache"
    module_file = _prepare_runtime_module(tmp_path, monkeypatch, module_name)
    page_cache.enable_read_tracking(root=tmp_path)

    try:
        with page_cache.record_reads() as reads:
            importlib.import_module(module_name)
    finally:
        _forget_modules(module_name)

    assert str(module_file.resolve()) in reads


def test_record_reads_tracks_executed_builtin_import(tmp_path, monkeypatch):
    package = tmp_path / "runtime_import_pkg"
    package.mkdir()
    (package / "__init__.py").write_text("")
    child = package / "child.py"
    child.write_text("VALUE = 1\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    _forget_modules("runtime_import_pkg", "runtime_import_pkg.child")
    importlib.invalidate_caches()
    page_cache.enable_read_tracking(root=tmp_path)

    try:
        with page_cache.record_reads() as reads:
            __import__("runtime_import_pkg.child")
    finally:
        _forget_modules("runtime_import_pkg", "runtime_import_pkg.child")

    assert str(child.resolve()) in reads


def test_read_tracking_root_change_invalidates_module_cache(tmp_path, monkeypatch):
    """Recording a module under one root must not leak into another root.

    The module-file cache is keyed by the raw ``__file__`` value (the hot path
    for every import statement), so switching recorder roots relies on
    ``enable_read_tracking`` clearing it.
    """
    root_a = tmp_path / "app_a"
    root_a.mkdir()
    root_b = tmp_path / "app_b"
    root_b.mkdir()
    module_name = "root_change_runtime_dep"
    module_file = _prepare_runtime_module(root_a, monkeypatch, module_name)
    page_cache.enable_read_tracking(root=root_a)

    try:
        with page_cache.record_reads() as reads_a:
            importlib.import_module(module_name)
        assert str(module_file.resolve()) in reads_a

        page_cache.enable_read_tracking(root=root_b)
        with page_cache.record_reads() as reads_b:
            importlib.import_module(module_name)
        assert str(module_file.resolve()) not in reads_b
    finally:
        _forget_modules(module_name)


def test_record_reads_tracks_path_open(tmp_path):
    """``Path.open`` calls ``io.open`` directly, bypassing the ``builtins.open``
    patch, so it must be patched itself for data reads to be recorded.
    """
    page_cache.enable_read_tracking(root=tmp_path)
    data = tmp_path / "content.md"
    data.write_text("hello")

    with page_cache.record_reads() as reads, data.open() as f:
        f.read()

    assert str(data.resolve()) in reads


def test_record_reads_ignores_path_open_writes(tmp_path):
    page_cache.enable_read_tracking(root=tmp_path)
    out = tmp_path / "out.md"

    with page_cache.record_reads() as reads, out.open("w") as f:
        f.write("x")

    assert str(out.resolve()) not in reads


def test_record_reads_ignores_unexecuted_import(tmp_path, monkeypatch):
    module_name = "uncalled_runtime_import_dep"
    module_file = _prepare_runtime_module(tmp_path, monkeypatch, module_name)
    page_cache.enable_read_tracking(root=tmp_path)

    def import_if_called():
        return importlib.import_module(module_name)

    with page_cache.record_reads() as reads:
        pass

    assert import_if_called
    assert str(module_file.resolve()) not in reads
    assert module_name not in sys.modules


def test_record_reads_no_recursion_when_recorder_import_triggers_import(
    tmp_path, monkeypatch
):
    """Recorder-internal imports must not re-enter dependency tracking."""
    module_name = "recorder_reentry_dep"
    module_file = _prepare_runtime_module(tmp_path, monkeypatch, module_name)
    page_cache.enable_read_tracking(root=tmp_path)

    real_absolute = Path.absolute

    def absolute_with_lazy_import(self: Path):
        __import__("ntpath")
        return real_absolute(self)

    monkeypatch.setattr(Path, "absolute", absolute_with_lazy_import)

    try:
        with page_cache.record_reads() as reads:
            importlib.import_module(module_name)
    finally:
        _forget_modules(module_name)

    assert str(module_file.resolve()) in reads
    assert not any("ntpath" in read for read in reads)


def test_record_reads_imports_only_project_modules(tmp_path):
    page_cache.enable_read_tracking(root=tmp_path)

    with page_cache.record_reads() as reads:
        importlib.import_module("json")

    assert reads == set()


def test_record_reads_tracks_symlinked_project_import(tmp_path, monkeypatch):
    import pytest

    root = tmp_path / "app"
    root.mkdir()
    module_name = "symlinked_runtime_dep"
    linked_root = tmp_path / "linked_app"
    try:
        linked_root.symlink_to(root, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable: {exc}")
    module_file = _prepare_runtime_module(
        root, monkeypatch, module_name, import_root=linked_root
    )
    page_cache.enable_read_tracking(root=root)

    try:
        with page_cache.record_reads() as reads:
            importlib.import_module(module_name)
    finally:
        _forget_modules(module_name)

    assert str(module_file.resolve()) in reads


def test_used_state_files_from_output_and_memos(tmp_path):
    from types import SimpleNamespace

    sfile = (tmp_path / "state.py").resolve()
    mfile = (tmp_path / "mstate.py").resolve()
    id_to_file = {
        "reflex___state____state____app_____s": sfile,
        "reflex___state____state____app_____m": mfile,
    }
    out = 'jsx("div",{},reflex___state____state____app_____s.x_rx_state_)'
    assert page_cache.used_state_files(out, [], id_to_file) == {sfile}
    assert page_cache.used_state_files("no state", [], id_to_file) == set()
    # state hidden inside an auto-memoized component is still captured
    memo = SimpleNamespace(
        render=lambda: {"contents": "reflex___state____state____app_____m.y_rx_state_"}
    )
    assert page_cache.used_state_files(out, [memo], id_to_file) == {sfile, mfile}
    # un-introspectable memo -> conservative (all fine files)
    boom = SimpleNamespace(render=lambda: (_ for _ in ()).throw(RuntimeError()))
    assert page_cache.used_state_files(out, [boom], id_to_file) == {sfile, mfile}


def test_file_validator_is_stat_first(tmp_path, monkeypatch):
    """Unchanged files are recognised from their stat key without being read."""
    f = tmp_path / "dep.py"
    f.write_text("x = 1\n")
    entry = page_cache.file_entry(str(f))
    assert entry is not None
    files = {str(f): entry}

    reads = 0
    original = page_cache.file_entry

    def counting(path):
        nonlocal reads
        reads += 1
        return original(path)

    monkeypatch.setattr(page_cache, "file_entry", counting)
    v = page_cache.FileValidator(files)
    assert v.changed(str(f)) is False
    assert reads == 0  # stat matched, never read
    assert v.unchanged([str(f)]) is True  # memoized, still no read
    assert reads == 0

    # Touched with identical content: hashed once, unchanged, entry refreshed.
    bumped = f.stat().st_mtime_ns + 1_000_000_000
    os.utime(f, ns=(bumped, bumped))
    v = page_cache.FileValidator(files)
    assert v.changed(str(f)) is False
    assert reads == 1
    assert v.refreshed[str(f)][1] == bumped

    # Same size, different content, distinct mtime: the hash decides.
    f.write_text("x = 2\n")
    os.utime(f, ns=(bumped, bumped))
    v = page_cache.FileValidator(files)
    assert v.changed(str(f)) is True
    # Unknown or missing files always count as changed.
    assert v.changed(str(tmp_path / "missing.py")) is True
    files[str(tmp_path / "gone.py")] = ["h", 1, 1]
    assert page_cache.FileValidator(files).changed(str(tmp_path / "gone.py")) is True


def test_import_names_parse_cache_skips_unchanged_files(tmp_path, monkeypatch):
    mod = tmp_path / "mod_a.py"
    mod.write_text("import os\nfrom pathlib import Path\n")
    page_cache._import_names_cache.clear()

    parses = 0
    import ast

    original = ast.parse

    def counting(*args, **kwargs):
        nonlocal parses
        parses += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(ast, "parse", counting)
    names = page_cache._module_import_names(str(mod), "mod_a")
    assert names == ["os", "pathlib", "pathlib.Path"]
    assert parses == 1
    assert page_cache._module_import_names(str(mod), "mod_a") == names
    assert parses == 1  # cached by stat key

    # The cache round-trips through its persisted form.
    exported = page_cache.export_import_names_cache()
    page_cache._import_names_cache.clear()
    page_cache.load_import_names_cache(exported)
    assert page_cache._module_import_names(str(mod), "mod_a") == names
    assert parses == 1
    # Malformed persisted entries are ignored, not fatal.
    page_cache.load_import_names_cache({str(mod): "garbage", "x": [[1], []]})
    assert page_cache._import_names_cache == {}

    # An edit re-parses.
    mod.write_text("import sys\n")
    assert page_cache._module_import_names(str(mod), "mod_a") == ["sys"]
    assert parses == 2


def test_first_party_roots_include_hot_reload_include_paths(tmp_path, monkeypatch):
    from reflex_base.environment import environment

    sibling = tmp_path / "sibling_pkg"
    sibling.mkdir()
    # Relative to cwd: the env var's ":" delimiter cannot carry a Windows
    # drive-letter path.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(environment.REFLEX_HOT_RELOAD_INCLUDE_PATHS.name, sibling.name)
    roots = page_cache.first_party_roots(tmp_path)
    assert roots == (tmp_path.resolve(), sibling.resolve())

    # A module under the include path is first-party for dependency tracking.
    page_cache.enable_read_tracking(root=tmp_path)
    module_file = sibling / "helper.py"
    module_file.write_text("VALUE = 1\n")
    assert page_cache._recordable_module_file(str(module_file)) == str(
        module_file.resolve()
    )
    assert page_cache._recordable_module_file(str(tmp_path / ".venv" / "x.py")) is None


def test_page_dependency_files_closes_over_dynamic_imports(tmp_path, monkeypatch):
    """A module imported at evaluation time brings its own import closure.

    The helper may already be loaded (an earlier page imported it), so its own
    imports never re-execute under the recorder; the graph supplies them.
    """
    from types import SimpleNamespace

    helper = _prepare_runtime_module(tmp_path, monkeypatch, "dyn_helper_for_closure")
    leaf = _prepare_runtime_module(tmp_path, monkeypatch, "dyn_leaf_for_closure")
    helper.write_text("import dyn_leaf_for_closure\n")
    try:
        importlib.import_module("dyn_helper_for_closure")
        page_cache.clear_import_graph()
        page_ctx = SimpleNamespace(
            root_component=SimpleNamespace(children=[]),
            output_code="",
            memo_contributions={},
            source_files={str(helper.resolve())},
        )
        deps = page_cache.page_dependency_files(
            cast(Any, page_ctx), lambda: None, {}, tmp_path
        )
    finally:
        _forget_modules("dyn_helper_for_closure", "dyn_leaf_for_closure")
        page_cache.clear_import_graph()

    assert str(helper.resolve()) in deps
    assert str(leaf.resolve()) in deps


def test_dynamic_import_records_parent_packages(tmp_path, monkeypatch):
    """Cached dynamic imports still depend on package initialization."""
    package = tmp_path / "review_dynamic_parent"
    package.mkdir()
    parent = package / "__init__.py"
    parent.write_text("VALUE = 1\n")
    child = package / "child.py"
    child.write_text("from . import VALUE\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    page_cache.enable_read_tracking(tmp_path)
    try:
        importlib.import_module("review_dynamic_parent.child")
        with page_cache.record_reads() as reads:
            importlib.import_module("review_dynamic_parent.child")
        assert {str(parent), str(child)} <= reads
    finally:
        _forget_modules("review_dynamic_parent", "review_dynamic_parent.child")


def test_package_relative_import_names(tmp_path):
    """Relative imports in package initializers resolve from that package."""
    source = tmp_path / "__init__.py"
    source.write_text("from . import helper\nfrom ..common import value\n")
    assert page_cache._module_import_names(str(source), "app.pages") == [
        "app.pages",
        "app.pages.helper",
        "app.common",
        "app.common.value",
    ]


def test_entrypoint_is_not_a_page_barrier(tmp_path, monkeypatch):
    """A page defined beside its App cannot hide app-wide configuration."""
    from types import SimpleNamespace

    entry = tmp_path / "app.py"
    entry.write_text("THEME = 'dark'\n")
    monkeypatch.setattr(page_cache, "_app_entrypoint_file", lambda root: entry)
    monkeypatch.setattr(
        page_cache, "build_import_graph", lambda root: {str(entry): set()}
    )
    monkeypatch.setattr(
        page_cache, "_component_source_files", lambda component, root: {str(entry)}
    )
    assert str(entry) in page_cache.app_dependency_files(
        [SimpleNamespace(component=None)], tmp_path
    )


def test_missing_read_remains_a_dependency(tmp_path, monkeypatch):
    """A handled missing read must invalidate when its file later appears."""
    missing = str(tmp_path / "optional.json")
    monkeypatch.setattr(page_cache, "page_dependency_files", lambda *args: {missing})
    files = {}
    deps = page_cache.page_dependency_entries(
        cast(Any, None), None, {}, page_cache.file_entry, files, tmp_path
    )
    assert deps == [missing]
    Path(missing).write_text("{}")
    assert not page_cache.FileValidator(files).unchanged(deps)


@pytest.mark.parametrize("statement", ["import", "import_module"])
def test_import_time_reads_are_recorded_for_every_importer(
    tmp_path, monkeypatch, statement
):
    """A module's import-time reads are deps of each page that imports it.

    Only the first page's import executes the module; a later page gets the
    cached module and must still depend on what its execution read.
    """
    data = tmp_path / "shared_data.json"
    data.write_text('{"title": "v1"}')
    _prepare_runtime_module(tmp_path, monkeypatch, "review_shared_helper").write_text(
        f"from pathlib import Path\nTITLE = Path({str(data)!r}).read_text()\n"
    )
    page_cache.enable_read_tracking(tmp_path)
    page_reads = []
    try:
        for _ in range(2):
            with page_cache.record_reads() as reads:
                if statement == "import":
                    exec("import review_shared_helper", {})
                else:
                    importlib.import_module("review_shared_helper")
            page_reads.append(reads)
    finally:
        _forget_modules("review_shared_helper")
    assert [str(data) in reads for reads in page_reads] == [True, True]


def test_entrypoint_digest_ignores_page_registrations_only(tmp_path):
    """Formatting, comments and top-level add_page calls do not change it."""
    entry = tmp_path / "entry_app.py"

    def digest(source: str) -> str | None:
        entry.write_text(source)
        return page_cache.entrypoint_digest(str(entry))

    base = digest(
        "import reflex as rx\nfrom .pages import a, b\n\napp = rx.App()\n"
        'app.add_page(a, route="/a")\n'
    )
    assert base is not None
    assert (
        digest(
            "import reflex as rx\nfrom .pages import a, b\n\n# pages\napp = rx.App()\n"
            'app.add_page(a, route="/a", title="A")\napp.add_page(b, route="/b")\n'
        )
        == base
    )
    assert (
        digest(
            "import reflex as rx\nfrom .pages import a, b\n\n"
            'app = rx.App(theme=rx.theme(accent_color="red"))\n'
            'app.add_page(a, route="/a")\n'
        )
        != base
    )
    assert digest("this is not python (") is None


def test_entrypoint_digest_ignores_imports_used_only_to_register_pages(tmp_path):
    """Importing a page only to register it is a registration; other imports count."""
    entry = tmp_path / "entry_app.py"

    def digest(source: str) -> str | None:
        entry.write_text(source)
        return page_cache.entrypoint_digest(str(entry))

    base = digest(
        "import reflex as rx\nfrom .themes import dark as theme\n"
        "from .pages.a import a\n\napp = rx.App(theme=theme)\n"
        'app.add_page(a, route="/a")\n'
    )
    assert (
        digest(
            "import reflex as rx\nfrom .themes import dark as theme\n"
            "from .pages.a import a\nfrom .pages.b import b\n\n"
            'app = rx.App(theme=theme)\napp.add_page(a, route="/a")\n'
            'app.add_page(b, route="/b")\n'
        )
        == base
    )
    # The same App call with a theme imported from elsewhere is another app.
    assert (
        digest(
            "import reflex as rx\nfrom .themes import light as theme\n"
            "from .pages.a import a\n\napp = rx.App(theme=theme)\n"
            'app.add_page(a, route="/a")\n'
        )
        != base
    )


_SLICED_MODULE = """\
import reflex as rx
from .other import unused

TITLE = "t"


class PageState(rx.State):
    value: int = 0


def helper():
    return rx.text(TITLE)


def page_a():
    return rx.box(helper(), PageState.value)


def page_b():
    return rx.text("b")
"""


@pytest.mark.parametrize(
    ("old", "new", "changes"),
    [
        ('rx.text("b")', 'rx.text("b2")', False),
        ("\n\ndef page_b", "\n\n# a comment\ndef page_b", False),
        ("def page_b", "def unrelated():\n    return 1\n\n\ndef page_b", False),
        ("from .other import unused\n", "", False),
        ("rx.box(helper()", "rx.vstack(helper()", True),
        ("rx.text(TITLE)", "rx.heading(TITLE)", True),
        ('TITLE = "t"', 'TITLE = "u"', True),
        ("value: int = 0", "value: int = 1", True),
        ("from .other import unused\n", "from .other import *\n", True),
    ],
)
def test_function_slice_digest_covers_what_the_function_reads(
    tmp_path, old, new, changes
):
    """A page function's slice changes only with the code it can read.

    That is its own body, the module-level functions it calls (transitively),
    every class, and every statement that runs at import.
    """
    module = tmp_path / "sliced.py"
    module.write_text(_SLICED_MODULE)
    before = page_cache.function_slice_digest(str(module), "page_a")
    assert before is not None
    module.write_text(_SLICED_MODULE.replace(old, new, 1))
    after = page_cache.function_slice_digest(str(module), "page_a")
    assert (after != before) is changes


@pytest.mark.parametrize(
    "source",
    [
        # A decorator can hand the function to code the page reads.
        (
            "REG = []\n\n\ndef register(f):\n    REG.append(f)\n    return f\n\n\n"
            "@register\ndef widget():\n    return 1\n\n\n"
            "def page_a():\n    return [f() for f in REG]\n"
        ),
        # Names reached through globals() are invisible to the syntax tree.
        (
            "def widget():\n    return 1\n\n\n"
            'def page_a():\n    return globals()["widget"]()\n'
        ),
    ],
)
def test_function_slice_digest_keeps_code_reached_indirectly(tmp_path, source):
    """Code the page reaches without naming it stays in the slice."""
    module = tmp_path / "indirect.py"
    module.write_text(source)
    before = page_cache.function_slice_digest(str(module), "page_a")
    module.write_text(source.replace("return 1", "return 2"))
    assert page_cache.function_slice_digest(str(module), "page_a") != before


def test_function_slice_digest_needs_a_top_level_function(tmp_path):
    """Only a module-level function has a slice."""
    module = tmp_path / "nested.py"
    module.write_text("def outer():\n    def inner():\n        return 1\n")
    assert page_cache.function_slice_digest(str(module), "inner") is None
    assert page_cache.function_slice_digest(str(tmp_path / "gone.py"), "x") is None


def test_entrypoint_digest_ignores_page_function_bodies(tmp_path):
    """A page defined beside its App is compared page by page, not globally."""
    entry = tmp_path / "entry_app.py"

    def digest(source: str) -> str | None:
        entry.write_text(source)
        return page_cache.entrypoint_digest(str(entry))

    source = (
        "import reflex as rx\n\n\ndef make_theme():\n    return rx.theme()\n\n\n"
        'def index():\n    return rx.text("a")\n\n\n'
        "app = rx.App(theme=make_theme())\n"
        'app.add_page(index, route="/")\n'
    )
    base = digest(source)
    assert base is not None
    assert digest(source.replace('rx.text("a")', 'rx.text("b")')) == base
    assert digest(source.replace("rx.theme()", "rx.theme(accent_color='red')")) != base


def test_page_dependency_files_track_the_page_function_slice(tmp_path, monkeypatch):
    """A page depends on its function's slice of its module, not the whole file."""
    from types import SimpleNamespace

    module = _prepare_runtime_module(tmp_path, monkeypatch, "sliced_pages_module")
    module.write_text(_SLICED_MODULE.replace("from .other import unused\n", ""))
    try:
        page_a = importlib.import_module("sliced_pages_module").page_a
        page_cache.clear_import_graph()
        page_ctx = SimpleNamespace(
            root_component=SimpleNamespace(children=[]),
            output_code="",
            memo_contributions={},
            source_files=set(),
        )
        deps = page_cache.page_dependency_files(
            cast(Any, page_ctx), page_a, {}, tmp_path
        )
    finally:
        _forget_modules("sliced_pages_module")
        page_cache.clear_import_graph()

    file = str(module.resolve())
    assert f"{file}{page_cache.SLICE_SEPARATOR}page_a" in deps
    assert file not in deps


def test_file_validator_compares_function_slices(tmp_path):
    """A slice dependency is stat-first and changes only with its slice."""
    module = tmp_path / "sliced.py"
    module.write_text(_SLICED_MODULE)
    dep = f"{module}{page_cache.SLICE_SEPARATOR}page_a"
    entry = page_cache.file_entry(dep)
    assert entry is not None
    files = {dep: entry}
    assert page_cache.FileValidator(files).unchanged([dep])
    module.write_text(_SLICED_MODULE.replace('rx.text("b")', 'rx.text("b2")'))
    validator = page_cache.FileValidator(files)
    assert validator.unchanged([dep])
    assert dep in validator.refreshed
    module.write_text(_SLICED_MODULE.replace("rx.box(", "rx.vstack("))
    assert not page_cache.FileValidator(files).unchanged([dep])
    assert page_cache.dep_file(dep) == str(module)
    assert page_cache.dep_file(str(module)) == str(module)
