"""Tests for the warm fork-per-compile dev compile daemon."""

import os

import pytest

from reflex.compiler import disk_cache
from reflex.utils import compile_daemon


def test_iter_source_files_picks_content_skips_build_dirs(tmp_path):
    (tmp_path / "page.py").write_text("x = 1\n")
    (tmp_path / "doc.md").write_text("# doc\n")
    (tmp_path / "guide.mdx").write_text("mdx\n")
    (tmp_path / "data.txt").write_text("ignored\n")  # not a watched suffix
    web = tmp_path / ".web"
    web.mkdir()
    (web / "build.js").write_text("// artifact\n")
    pycache = tmp_path / "__pycache__"
    pycache.mkdir()
    (pycache / "stale.py").write_text("# compiled\n")

    found = {p.name for p in compile_daemon._iter_source_files(tmp_path)}
    assert found == {"page.py", "doc.md", "guide.mdx"}


def test_external_dependency_files_includes_sibling_markdown(tmp_path, monkeypatch):
    """A page's markdown read from a sibling dir (outside the app root) is watched.

    This is the regression for markdown edits never triggering a reload: such
    files live outside ``get_reload_paths`` and are only known via the compile
    manifest's per-page dependency sets.
    """
    app_root = tmp_path / "app"
    app_root.mkdir()
    own_module = app_root / "page.py"
    own_module.write_text("x = 1\n")
    sibling_md = tmp_path / "docs" / "guide.md"
    sibling_md.parent.mkdir()
    sibling_md.write_text("# guide\n")

    manifest = {
        "pages": {
            "/g": {
                "dep_hashes": {
                    str(own_module): "h1",  # under the app root -> not external
                    str(sibling_md): "h2",  # sibling dir -> must be watched
                }
            }
        }
    }
    monkeypatch.setattr(disk_cache, "load_manifest", lambda: manifest)

    external = compile_daemon._external_dependency_files([app_root.resolve()])
    assert sibling_md.resolve() in external
    assert own_module.resolve() not in external


def test_external_dependency_files_empty_without_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(disk_cache, "load_manifest", lambda: None)
    assert compile_daemon._external_dependency_files([tmp_path]) == set()


def test_snapshot_detects_external_markdown_change(tmp_path, monkeypatch):
    """The watch snapshot includes sibling markdown and reflects its mtime change."""
    app_root = tmp_path / "app"
    app_root.mkdir()
    (app_root / "page.py").write_text("x = 1\n")
    sibling_md = tmp_path / "docs" / "guide.md"
    sibling_md.parent.mkdir()
    sibling_md.write_text("# v1\n")
    monkeypatch.setattr(
        disk_cache,
        "load_manifest",
        lambda: {"pages": {"/g": {"dep_hashes": {str(sibling_md): "h"}}}},
    )

    roots = [app_root.resolve()]
    external = compile_daemon._external_dependency_files(roots)
    snap1 = compile_daemon._snapshot(
        compile_daemon._watch_paths(roots, tmp_path, external)
    )
    assert sibling_md.resolve() in snap1
    assert (app_root / "page.py").resolve() in snap1

    # Force a distinct mtime (deterministic, independent of fs mtime resolution).
    bumped = snap1[sibling_md.resolve()] + 1_000_000_000
    os.utime(sibling_md, ns=(bumped, bumped))
    snap2 = compile_daemon._snapshot(
        compile_daemon._watch_paths(roots, tmp_path, external)
    )
    assert snap2[sibling_md.resolve()] != snap1[sibling_md.resolve()]


def test_first_party_module_names_includes_namespace_packages(tmp_path, monkeypatch):
    """Namespace packages (no ``__file__``) are captured for purge by name.

    Regression: a namespace package left in ``sys.modules`` after its regular
    siblings were purged broke re-import with a ``KeyError`` on the parent path.
    They are now identified by sharing a first-party top-level name (derived from
    a regular sibling's ``__file__``), never by their lazy ``__path__``.
    """
    import importlib
    import sys

    nspkg = tmp_path / "ns_under_test"
    nspkg.mkdir()  # no __init__.py -> namespace package
    (nspkg / "leaf.py").write_text("Y = 1\n")  # regular submodule with __file__
    monkeypatch.syspath_prepend(str(tmp_path))
    try:
        pkg = importlib.import_module("ns_under_test")
        importlib.import_module("ns_under_test.leaf")
        assert getattr(pkg, "__file__", None) is None  # confirm it's a namespace pkg

        names = compile_daemon._first_party_module_names([tmp_path.resolve()])
        assert "ns_under_test" in names  # namespace pkg captured by name
        assert "ns_under_test.leaf" in names  # regular module captured via __file__
    finally:
        sys.modules.pop("ns_under_test", None)
        sys.modules.pop("ns_under_test.leaf", None)


@pytest.mark.skipif(not hasattr(os, "fork"), reason="requires os.fork (POSIX)")
def test_reset_model_metadata_allows_table_redefinition():
    """After reset, an ``rx.Model`` table can be redefined without conflict.

    Regression: the forked child inherits the warm, populated SQLAlchemy
    ``MetaData``; re-evaluating a page that defines a model raised
    ``Table '...' is already defined``. Run in a fork so clearing the global
    metadata can't affect the test process.
    """
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:  # child
        os.close(read_fd)
        result = b"E"
        try:
            import warnings

            warnings.simplefilter("ignore")
            import reflex as rx

            def _define():
                class DaemonResetUser(rx.Model, table=True):
                    name: str

            _define()
            compile_daemon._reset_model_metadata()
            _define()  # must NOT raise "Table 'daemonresetuser' is already defined"
            result = b"1"
        except Exception:
            import traceback

            traceback.print_exc()
        finally:
            os.write(write_fd, result)
            os.close(write_fd)
            os._exit(0)

    os.close(write_fd)
    out = os.read(read_fd, 1)
    os.close(read_fd)
    os.waitpid(pid, 0)
    assert out == b"1"


@pytest.mark.skipif(not hasattr(os, "fork"), reason="requires os.fork (POSIX)")
def test_reset_first_party_purges_modules_and_registries(tmp_path):
    """``_reset_first_party`` purges first-party modules and clears registries.

    Runs in a forked child so the global-registry reset can't corrupt the test
    process — exactly how the daemon uses it (a throwaway child per compile).
    """
    mod_file = tmp_path / "fp_module.py"
    mod_file.write_text("VALUE = 1\n")

    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:  # child
        os.close(read_fd)
        result = b"E"
        try:
            import importlib.util
            import sys

            spec = importlib.util.spec_from_file_location(
                "fp_module_under_test", mod_file
            )
            assert spec is not None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # type: ignore[union-attr]
            sys.modules["fp_module_under_test"] = module

            from reflex_base.registry import RegistrationContext

            from reflex.page import DECORATED_PAGES
            from reflex.state import all_base_state_classes

            RegistrationContext.ensure_context().base_states["sentinel"] = object()  # type: ignore[assignment]
            all_base_state_classes["sentinel"] = None
            DECORATED_PAGES["sentinel_app"].append((lambda: None, {}))

            compile_daemon._reset_first_party([tmp_path.resolve()])

            purged = "fp_module_under_test" not in sys.modules
            cleared = (
                not RegistrationContext.ensure_context().base_states
                and not all_base_state_classes
                and not DECORATED_PAGES
            )
            result = b"1" if (purged and cleared) else b"0"
        except Exception:
            import traceback

            traceback.print_exc()
        finally:
            os.write(write_fd, result)
            os.close(write_fd)
            os._exit(0)

    os.close(write_fd)
    out = os.read(read_fd, 1)
    os.close(read_fd)
    os.waitpid(pid, 0)
    assert out == b"1"
