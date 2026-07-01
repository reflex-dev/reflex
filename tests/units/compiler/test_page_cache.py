"""Tests for the per-page dependency graph used by the incremental compile cache."""

import importlib
import sys
from pathlib import Path

from reflex.compiler import page_cache


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
