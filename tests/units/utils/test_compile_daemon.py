"""Tests for the warm fork-per-compile dev compile daemon."""

import contextlib
import errno
import os
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

import reflex as rx
from reflex.compiler import disk_cache
from reflex.testing import AppHarness
from reflex.utils import compile_daemon


class _SurvivingModuleState(rx.State):
    """Module-level state, like one from a non-purged installed package."""

    b: int = 0


def test_can_fork_rejects_remaining_native_threads(monkeypatch):
    """Native threads must force the subprocess fallback after the grace period."""
    monkeypatch.setattr(compile_daemon, "_quiesce_parent", lambda: None)
    monkeypatch.setattr(compile_daemon.threading, "active_count", lambda: 1)
    monkeypatch.setattr(compile_daemon, "_os_thread_count", lambda: 8)
    ticks = iter([0.0, 1.0])
    monkeypatch.setattr(compile_daemon.time, "monotonic", lambda: next(ticks))
    assert not compile_daemon._can_fork()


def test_missed_changes_includes_new_sources_and_assets(tmp_path):
    """Catch sources and assets created while the OS watcher is stopped."""
    state = compile_daemon._WatchState(roots=[tmp_path], root=tmp_path)
    before = compile_daemon._dependency_snapshot(state)
    source = tmp_path / "new_page.py"
    source.write_text("VALUE = 1\n")
    assets = tmp_path / "assets"
    assets.mkdir()
    asset = assets / "image.txt"
    asset.write_text("new asset")
    after = compile_daemon._dependency_snapshot(state)
    assert {source, asset} <= compile_daemon._missed_changes(before, after)


def test_next_changes_catches_edit_before_watcher_starts(tmp_path, monkeypatch):
    """Reconcile the previous snapshot after the watcher has subscribed."""
    import watchfiles

    state = compile_daemon._WatchState(roots=[tmp_path], root=tmp_path)
    state.checkpoint = compile_daemon._dependency_snapshot(state)
    source = tmp_path / "new_page.py"
    source.write_text("VALUE = 1\n")

    def watch(*args, **kwargs):
        """Simulate a watcher timeout with no event for the earlier edit.

        Yields:
            An empty event batch.
        """
        yield set()

    monkeypatch.setattr(watchfiles, "watch", watch)
    assert compile_daemon._next_changes(state, lambda: True) == {source}


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


def test_under_roots_matches_only_real_ancestors(tmp_path):
    root = tmp_path / "app"
    roots = [root]
    assert compile_daemon._under_roots(root, roots)
    assert compile_daemon._under_roots(root / "pages" / "index.py", roots)
    # A sibling sharing the root's string prefix is NOT under it.
    assert not compile_daemon._under_roots(tmp_path / "app_extra" / "m.py", roots)
    assert not compile_daemon._under_roots(tmp_path / "other.py", roots)
    # The root's own parent is not under it either.
    assert not compile_daemon._under_roots(tmp_path, roots)


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
                "deps": [
                    str(own_module),  # under the app root -> not external
                    str(sibling_md),  # sibling dir -> must be watched
                ]
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
        lambda: {"pages": {"/g": {"deps": [str(sibling_md)]}}},
    )

    roots = [app_root.resolve()]
    state = compile_daemon._WatchState.build(roots, tmp_path.resolve())
    snap1 = compile_daemon._snapshot(state.watch_paths())
    assert sibling_md.resolve() in snap1
    assert (app_root / "page.py").resolve() in snap1
    # The OS watcher is pointed at the sibling directory too.
    assert sibling_md.resolve().parent in state.targets()

    # Force a distinct mtime (deterministic, independent of fs mtime resolution).
    bumped = snap1[sibling_md.resolve()] + 1_000_000_000
    os.utime(sibling_md, ns=(bumped, bumped))
    snap2 = compile_daemon._snapshot(state.watch_paths())
    assert snap2[sibling_md.resolve()] != snap1[sibling_md.resolve()]


def test_watch_state_accepts_only_compile_inputs(tmp_path, monkeypatch):
    """Recorded data deps of any suffix count; build output never does."""
    app_root = tmp_path / "app"
    app_root.mkdir()
    data = app_root / "table.json"
    data.write_text("{}")
    monkeypatch.setattr(
        disk_cache, "load_manifest", lambda: {"pages": {"/t": {"deps": [str(data)]}}}
    )
    (tmp_path / "assets").mkdir()
    state = compile_daemon._WatchState.build([app_root.resolve()], tmp_path.resolve())

    assert state.accepts(app_root / "page.py")
    assert state.accepts(app_root / "guide.md")
    assert state.accepts(data)  # not a watched suffix, but a recorded dependency
    assert state.accepts(tmp_path / "assets" / "logo.svg")
    assert not state.accepts(app_root / "other.json")  # unrecorded data file
    assert not state.accepts(tmp_path / ".web" / "app" / "routes" / "x.jsx")
    assert not state.accepts(tmp_path / "elsewhere" / "page.py")  # outside roots


def test_iter_changes_reports_an_edit(tmp_path):
    """The OS watcher reports an edited source file (no polling involved)."""
    import threading
    import time

    pytest.importorskip("watchfiles")
    app_root = tmp_path / "app"
    app_root.mkdir()
    page = app_root / "page.py"
    page.write_text("x = 1\n")
    state = compile_daemon._WatchState([app_root.resolve()], tmp_path.resolve())
    got: list[set] = []

    def run() -> None:
        changed = compile_daemon._next_changes(state, lambda: not got)
        if changed:
            got.append(changed)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not got and time.monotonic() < deadline:
        page.write_text(f"x = {time.monotonic()}\n")
        time.sleep(0.2)
    thread.join(5)
    assert got
    assert page.resolve() in {p.resolve() for p in got[0]}
    # The native watcher thread is gone, so the daemon may fork again.
    assert not any("watchfiles" in t.name.lower() for t in threading.enumerate())


def test_missed_changes_catches_edits_during_compile(tmp_path):
    a, b = tmp_path / "a.py", tmp_path / "b.py"
    a.write_text("1")
    b.write_text("1")
    state = compile_daemon._WatchState([tmp_path], tmp_path, known={a, b})
    before = compile_daemon._dependency_snapshot(state)
    bumped = before[b] + 1_000_000_000
    os.utime(b, ns=(bumped, bumped))
    c = tmp_path / "c.py"
    c.write_text("1")
    state.known.add(c)
    after = compile_daemon._dependency_snapshot(state)
    assert compile_daemon._missed_changes(before, after) == {b, c}
    assert compile_daemon._missed_changes(after, after) == set()


def test_wait_for_compile_respects_lock(tmp_path, monkeypatch):
    import time

    from reflex.utils import path_ops

    monkeypatch.setattr("reflex.utils.prerequisites.get_backend_dir", lambda: tmp_path)
    monkeypatch.setattr(compile_daemon, "daemon_active", lambda: True)
    # No compile in progress -> returns at once.
    start = time.monotonic()
    compile_daemon.wait_for_compile(timeout=1)
    assert time.monotonic() - start < 0.2
    # A compile in progress -> waits until it finishes (or the timeout).
    with compile_daemon._compile_lock(tmp_path):
        start = time.monotonic()
        compile_daemon.wait_for_compile(timeout=0.3)
        assert time.monotonic() - start >= 0.3
    # A lock file nobody holds (a compile killed mid-way) is not waited on,
    # even when it holds the pid of a live process.
    lock = compile_daemon._lock_path()
    lock.write_text(str(os.getpid()))
    assert not path_ops.is_locked(lock)
    start = time.monotonic()
    compile_daemon.wait_for_compile(timeout=5)
    assert time.monotonic() - start < 0.5
    # A daemon that exits mid-wait releases the worker.
    monkeypatch.setattr(compile_daemon, "daemon_active", lambda: False)
    with compile_daemon._compile_lock(tmp_path):
        start = time.monotonic()
        compile_daemon.wait_for_compile(timeout=5)
        assert time.monotonic() - start < 0.5


@pytest.mark.parametrize("blocked_attempts", [1, 2])
def test_record_built_inputs_retries_windows_readers(
    tmp_path, monkeypatch, blocked_attempts
):
    """Publish the new record after Windows readers release the old record."""
    monkeypatch.setattr("reflex.utils.prerequisites.get_backend_dir", lambda: tmp_path)
    monkeypatch.setattr(compile_daemon.constants, "IS_WINDOWS", True)
    page = tmp_path / "page.py"
    page.write_text("v1")
    built = compile_daemon._snapshot({page})
    compile_daemon._record_built_inputs(built)
    record = compile_daemon._built_inputs_path()
    previous_record = record.read_text()
    mtime = built[page] + 1_000_000_000
    os.utime(page, ns=(mtime, mtime))
    replace = Path.replace
    attempts = 0

    def replace_after_reader_closes(source, target):
        """Keep the previous record intact while a reader blocks replacement.

        Args:
            source: Temporary record to publish.
            target: Destination record.

        Returns:
            The destination after the reader releases it.

        Raises:
            PermissionError: While the reader still holds the destination open.
        """
        nonlocal attempts
        attempts += 1
        assert record.read_text() == previous_record
        assert not compile_daemon._built_inputs_current()
        if attempts <= blocked_attempts:
            raise PermissionError(errno.EACCES, "Reader still has the record open")
        return replace(source, target)

    monkeypatch.setattr(Path, "replace", replace_after_reader_closes)
    sleep = Mock()
    monkeypatch.setattr(compile_daemon.time, "sleep", sleep)
    compile_daemon._record_built_inputs(compile_daemon._snapshot({page}))
    assert compile_daemon._built_inputs_current()
    assert sleep.call_count == blocked_attempts
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize(
    ("is_windows", "error", "attempts"),
    [
        (True, PermissionError(errno.EACCES, "Access denied"), 3),
        (False, PermissionError(errno.EACCES, "Access denied"), 1),
        (True, OSError(errno.ENOSPC, "No space left"), 1),
    ],
)
def test_record_built_inputs_propagates_errors(
    tmp_path, monkeypatch, is_windows, error, attempts
):
    """Bound retries, retain the old record, and remove a failed temporary write."""
    monkeypatch.setattr("reflex.utils.prerequisites.get_backend_dir", lambda: tmp_path)
    monkeypatch.setattr(compile_daemon.constants, "IS_WINDOWS", is_windows)
    compile_daemon._record_built_inputs({})
    record = compile_daemon._built_inputs_path()
    previous_record = record.read_text()
    replace = Mock(side_effect=error)
    monkeypatch.setattr(Path, "replace", replace)
    sleep = Mock()
    monkeypatch.setattr(compile_daemon.time, "sleep", sleep)
    with pytest.raises(type(error)) as raised:
        compile_daemon._record_built_inputs({tmp_path / "page.py": 1})
    assert raised.value is error
    assert replace.call_count == attempts
    assert sleep.call_count == attempts - 1
    assert record.read_text() == previous_record
    assert not list(tmp_path.glob("*.tmp"))


def test_wait_for_compile_waits_for_unbuilt_edits(tmp_path, monkeypatch):
    """Without a lock, a worker still waits while a built input has changed.

    The daemon takes its lock only once its watcher reports the edit, so a
    worker that restarts first would read the previous stateful-pages marker.
    """
    import threading
    import time

    monkeypatch.setattr("reflex.utils.prerequisites.get_backend_dir", lambda: tmp_path)
    monkeypatch.setattr(compile_daemon, "daemon_active", lambda: True)
    page = tmp_path / "page.py"
    page.write_text("v1")
    built = compile_daemon._snapshot({page})
    compile_daemon._record_built_inputs(built)
    start = time.monotonic()
    compile_daemon.wait_for_compile(timeout=1)
    assert time.monotonic() - start < 0.2
    mtime = built[page] + 1_000_000_000
    os.utime(page, ns=(mtime, mtime))
    start = time.monotonic()
    compile_daemon.wait_for_compile(timeout=0.3)
    assert time.monotonic() - start >= 0.3
    # The daemon builds the edit: the worker proceeds.
    timer = threading.Timer(
        0.1, compile_daemon._record_built_inputs, [compile_daemon._snapshot({page})]
    )
    timer.start()
    start = time.monotonic()
    try:
        compile_daemon.wait_for_compile(timeout=5)
        assert time.monotonic() - start < 1
        assert compile_daemon._built_inputs_current()
    finally:
        timer.join()


def test_first_party_module_names_caches_file_classification(tmp_path, monkeypatch):
    """Module files are classified once; a repeat pass resolves no paths."""
    import sys
    import types

    mod = types.ModuleType("fp_cached_mod")
    mod.__file__ = str(tmp_path / "pkg" / "cached_mod.py")
    monkeypatch.setitem(sys.modules, "fp_cached_mod", mod)
    roots = [tmp_path.resolve()]
    assert "fp_cached_mod" in compile_daemon._first_party_module_names(roots)
    assert compile_daemon._first_party_file_cache[mod.__file__] is True

    calls = 0
    original = Path.resolve

    def counting_resolve(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", counting_resolve)
    assert "fp_cached_mod" in compile_daemon._first_party_module_names(roots)
    assert calls == 0


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


def test_reset_model_metadata_skips_unloaded_model_layers(monkeypatch):
    """A child of an app that never loaded the model layer does not import it.

    Importing it only to clear its registries cost every hot reload ~0.3 s.
    """
    for name in ("sqlmodel", "reflex.model"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    compile_daemon._reset_model_metadata()
    assert "sqlmodel" not in sys.modules
    assert "reflex.model" not in sys.modules


@pytest.mark.skipif(not hasattr(os, "fork"), reason="requires os.fork (POSIX)")
def test_reset_model_metadata_allows_table_redefinition():
    """After reset, an ``rx.Model`` table can be redefined without conflict.

    Regression: the forked child inherits the warm, populated SQLAlchemy
    ``MetaData``; re-evaluating a page that defines a model raised
    ``Table '...' is already defined``. Run in a fork so clearing the global
    metadata can't affect the test process.
    """
    # ``rx.Model(table=True)`` needs the SQLModel stack; the db-less unit-test
    # job uninstalls it, so skip there rather than fail on the first definition.
    pytest.importorskip("sqlmodel")

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
def test_reset_first_party_keeps_surviving_module_states(tmp_path):
    """States from modules that survive the purge stay registered.

    A class body in a non-purged module (framework internals, installed or
    workspace packages like reflex_site_shared) never re-executes in the child,
    so dropping its registration loses the state from the app's state tree —
    and from the compiled contexts file — breaking the frontend's dispatch map.
    Purged-module states and runtime-created ``reflex.istate.dynamic`` states
    must still be dropped (they re-register on re-import/re-evaluation), and
    the dynamic module's attributes must be reset so re-created local states
    get their deterministic fresh-process names, matching the cold backend.
    """
    mod_file = tmp_path / "purged_state_mod.py"
    mod_file.write_text(
        "import reflex as rx\n\nclass PurgedState(rx.State):\n    a: int = 0\n"
    )

    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:  # child
        os.close(read_fd)
        result = b"E"
        try:
            import importlib.util
            import sys

            import reflex.istate.dynamic as istate_dynamic
            from reflex.state import State, all_base_state_classes

            spec = importlib.util.spec_from_file_location("purged_state_mod", mod_file)
            assert spec is not None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # type: ignore[union-attr]
            sys.modules["purged_state_mod"] = module

            def _local_state() -> type[rx.State]:
                class LocalState(rx.State):
                    c: int = 0

                return LocalState

            local_cls = _local_state()
            assert local_cls.__module__ == istate_dynamic.__name__
            local_name = local_cls.__name__

            compile_daemon._reset_first_party([tmp_path.resolve()])

            substate_names = {c.__name__ for c in State.get_substates()}
            surviving_kept = (
                "_SurvivingModuleState" in substate_names
                and _SurvivingModuleState.get_full_name() in all_base_state_classes
            )
            purged_dropped = (
                "purged_state_mod" not in sys.modules
                and "PurgedState" not in substate_names
            )
            dynamic_dropped = local_name not in substate_names and not [
                n for n in vars(istate_dynamic) if not n.startswith("__")
            ]
            # A re-created local state gets its original (fresh-process) name,
            # not a collision-suffixed drift.
            redefined_deterministic = _local_state().__name__ == local_name

            result = (
                b"1"
                if (
                    surviving_kept
                    and purged_dropped
                    and dynamic_dropped
                    and redefined_deterministic
                )
                else b"0"
            )
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

    Runs in a forked child so the registry reset cannot affect the test process.
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

            from reflex.state import all_base_state_classes

            RegistrationContext.ensure_context().base_states["sentinel"] = object()  # type: ignore[assignment]
            all_base_state_classes["sentinel"] = None
            RegistrationContext.ensure_context().decorated_pages.append((
                lambda: None,
                {},
            ))

            compile_daemon._reset_first_party([tmp_path.resolve()])

            purged = "fp_module_under_test" not in sys.modules
            # The sentinel (a bare object, no surviving module) must be dropped;
            # real states from surviving modules are kept (see the test above).
            cleared = (
                "sentinel" not in RegistrationContext.ensure_context().base_states
                and "sentinel" not in all_base_state_classes
                and not RegistrationContext.ensure_context().decorated_pages
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


def test_quiesce_parent_stops_telemetry_worker():
    """The telemetry worker must not keep the daemon parent multi-threaded.

    The initial compile sends a telemetry event, whose executor thread would
    otherwise outlive it and make every later fork check fail silently.
    """
    import threading

    from reflex.utils import telemetry

    telemetry._get_telemetry_executor().submit(lambda: None).result()
    assert any(t.name.startswith("reflex-telemetry") for t in threading.enumerate())

    compile_daemon._quiesce_parent()

    assert telemetry._executor is None
    assert not any(t.name.startswith("reflex-telemetry") for t in threading.enumerate())
    # A later send lazily recreates a worker, so shutdown is not one-way.
    telemetry._get_telemetry_executor().submit(lambda: None).result()
    telemetry.shutdown_executor()
    assert telemetry._executor is None


def test_owns_compilation_follows_the_daemon_lock(tmp_path, monkeypatch):
    """Backend workers defer to a daemon holding its lock; the daemon always owns."""
    from reflex_base.environment import environment

    from reflex.utils import path_ops

    monkeypatch.setattr("reflex.utils.prerequisites.get_backend_dir", lambda: tmp_path)
    monkeypatch.delenv(environment.REFLEX_COMPILE_DAEMON.name, raising=False)
    # No daemon: a plain process compiles as usual.
    assert compile_daemon.daemon_active() is False
    assert compile_daemon.owns_compilation() is True
    # A lock file nobody holds (a killed daemon, a copied .web) names no owner,
    # even when it holds the pid of a live process.
    lock = compile_daemon._daemon_lock_path()
    lock.write_text(str(os.getpid()))
    assert compile_daemon.daemon_active() is False
    # A daemon holding the lock: workers stand down.
    descriptor = path_ops.try_lock(lock)
    assert descriptor is not None
    try:
        assert compile_daemon.daemon_active() is True
        assert compile_daemon.owns_compilation() is False
        # ...but the daemon's own processes still own the build.
        monkeypatch.setenv(environment.REFLEX_COMPILE_DAEMON.name, "1")
        assert compile_daemon.owns_compilation() is True
    finally:
        os.close(descriptor)
    monkeypatch.delenv(environment.REFLEX_COMPILE_DAEMON.name)
    assert compile_daemon.owns_compilation() is True


def test_failed_daemon_spawn_propagates(monkeypatch):
    """A failed spawn raises out of the run scope, leaving workers in charge."""

    def fail(*args, **kwargs):
        """Simulate failure to launch the child."""
        message = "spawn failed"
        raise OSError(message)

    monkeypatch.setattr(compile_daemon.subprocess, "Popen", fail)
    with pytest.raises(OSError, match="spawn failed"), compile_daemon.running():
        pass


@pytest.mark.parametrize("exit_with", [None, KeyboardInterrupt])
def test_daemon_stops_when_the_run_scope_exits(tmp_path, monkeypatch, exit_with):
    """Leaving the ``reflex run`` scope stops the daemon, however the run ends.

    A signal to ``reflex run`` alone (an IDE stop, ``kill``) must not leave the
    run waiting on a daemon that never got the signal.
    """
    import subprocess

    monkeypatch.setattr("reflex.utils.prerequisites.get_backend_dir", lambda: tmp_path)
    lock = compile_daemon._daemon_lock_path()
    popen = subprocess.Popen
    spawned: list[subprocess.Popen] = []

    def spawn_holder(args, **kwargs):
        """Stand in for the daemon: hold its lock and never exit on its own.

        Args:
            args: The daemon command (replaced).
            kwargs: The Popen options.

        Returns:
            The spawned process.
        """
        holder = (
            "import time\n"
            "from pathlib import Path\n"
            "from reflex.utils import path_ops\n"
            f"assert path_ops.try_lock(Path({str(lock)!r})) is not None\n"
            "print('held', flush=True)\n"
            "time.sleep(60)\n"
        )
        proc = popen(
            [sys.executable, "-c", holder], stdout=subprocess.PIPE, text=True, **kwargs
        )
        spawned.append(proc)
        return proc

    monkeypatch.setattr(compile_daemon.subprocess, "Popen", spawn_holder)
    with (
        contextlib.suppress(KeyboardInterrupt),
        compile_daemon.running(),
    ):
        [proc] = spawned
        assert proc.stdout is not None
        assert proc.stdout.readline().strip() == "held"
        assert compile_daemon.daemon_active()
        if exit_with is not None:
            raise exit_with
    [proc] = spawned
    assert proc.poll() is not None
    # Windows can release byte-range locks asynchronously after process exit.
    assert AppHarness._poll_for(lambda: not compile_daemon.daemon_active(), timeout=5)


def test_watch_state_discovers_new_project_root_sources(tmp_path):
    """Watching existing children must not hide newly created siblings."""
    existing = tmp_path / "app"
    existing.mkdir()
    state = compile_daemon._WatchState(roots=[existing], root=tmp_path)
    source = tmp_path / "new_helper.py"
    assert tmp_path in state.targets()
    assert state.accepts(source)
    source.write_text("VALUE = 1")
    assert source in state.watch_paths()


def test_watcher_preserves_snapshot_before_teardown(tmp_path, monkeypatch):
    """An edit during watcher teardown must be caught after compilation."""
    import watchfiles

    source = tmp_path / "page.py"
    source.write_text("before")
    state = compile_daemon._WatchState(roots=[tmp_path], root=tmp_path)
    state.checkpoint = compile_daemon._dependency_snapshot(state)

    def watch(*args, **kwargs):
        """Emit an edit, then mutate another input as the watcher closes.

        Yields:
            A filesystem event batch.
        """
        try:
            source.write_text("first edit")
            yield {(2, str(source))}
        finally:
            (tmp_path / "late.py").write_text("late edit")

    monkeypatch.setattr(watchfiles, "watch", watch)
    assert compile_daemon._next_changes(state, lambda: True) == {source}
    assert source not in compile_daemon._missed_changes(
        state.checkpoint, compile_daemon._dependency_snapshot(state)
    )
    assert tmp_path / "late.py" in compile_daemon._missed_changes(
        state.checkpoint, compile_daemon._dependency_snapshot(state)
    )


@pytest.mark.parametrize("warm_only", [False, True])
def test_daemon_initial_work_holds_lock(tmp_path, monkeypatch, warm_only):
    """Startup either warms or compiles, always under the backend wait lock."""
    from reflex.utils import path_ops, prerequisites

    lock = tmp_path / "compile.lock"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(compile_daemon, "_lock_path", lambda: lock)
    monkeypatch.setattr(compile_daemon, "_reload_roots", lambda: [tmp_path])
    monkeypatch.setattr(compile_daemon, "_prepare_fork_parent", lambda roots: None)
    monkeypatch.setattr(compile_daemon, "_next_changes", lambda *args: None)
    monkeypatch.setattr(
        compile_daemon._WatchState,
        "build",
        lambda *args: compile_daemon._WatchState([tmp_path], tmp_path),
    )
    calls = []

    def compile_app(**kwargs):
        """Verify initial compilation blocks backend readers."""
        calls.append(("compile", path_ops.is_locked(lock)))

    def import_app(**kwargs):
        """Verify warm startup only imports the application."""
        calls.append(("import", path_ops.is_locked(lock)))

    monkeypatch.setattr(prerequisites, "get_compiled_app", compile_app)
    monkeypatch.setattr(prerequisites, "get_app", import_app)
    if warm_only:
        monkeypatch.setenv("REFLEX_COMPILE_DAEMON_PRECOMPILED", "1")
    else:
        monkeypatch.delenv("REFLEX_COMPILE_DAEMON_PRECOMPILED", raising=False)
    compile_daemon._serve()
    assert calls == [("import" if warm_only else "compile", True)]
    assert not path_ops.is_locked(lock)
    assert "REFLEX_COMPILE_DAEMON_PRECOMPILED" not in os.environ


def test_watcher_reconciles_edits_after_an_idle_batch(tmp_path, monkeypatch):
    """A late edit must be included even if its OS event is in a later batch."""
    import watchfiles

    first = tmp_path / "first.py"
    second = tmp_path / "second.py"
    first.write_text("old")
    second.write_text("old")
    state = compile_daemon._WatchState([tmp_path], tmp_path)
    state.checkpoint = compile_daemon._dependency_snapshot(state)

    def watch(*args, **kwargs):
        """Return one event while another changed input awaits its event batch.

        Yields:
            An idle batch, followed by the first file's event.
        """
        yield set()
        first.write_text("new first")
        second.write_text("new second")
        yield {(2, str(first))}

    monkeypatch.setattr(watchfiles, "watch", watch)
    assert compile_daemon._next_changes(state, lambda: True) == {first, second}


def test_serve_keeps_failed_changes_pending_until_a_compile_succeeds(
    tmp_path, monkeypatch
):
    """Paths from a failed compile are re-reported with the next change batch.

    The manifest is only refreshed by a successful compile, so a path that
    missed a failed build is still a stale dependency: dropping it from the
    changed hint would let the stat-free hit shortcut reuse its page.
    """
    from reflex.utils import prerequisites

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(compile_daemon, "_lock_path", lambda: tmp_path / "lock")
    monkeypatch.setattr(compile_daemon, "_reload_roots", lambda: [tmp_path])
    monkeypatch.setattr(compile_daemon, "_prepare_fork_parent", lambda roots: None)
    monkeypatch.setattr(prerequisites, "get_app", lambda **kwargs: None)
    monkeypatch.setenv("REFLEX_COMPILE_DAEMON_PRECOMPILED", "1")
    monkeypatch.setattr(
        compile_daemon._WatchState,
        "build",
        lambda *args: compile_daemon._WatchState([tmp_path], tmp_path),
    )
    a, b = tmp_path / "a.py", tmp_path / "b.py"
    batches = iter([{a, b}, {b}, {a}, None])
    monkeypatch.setattr(compile_daemon, "_next_changes", lambda *args: next(batches))
    compiles: list[set[Path]] = []

    def compile_once(roots, prerender_routes, changed=None):
        """Fail the first compile, succeed afterwards.

        Args:
            roots: The reload roots.
            prerender_routes: Whether to prerender routes.
            changed: The changed-path hint handed to the compile.

        Returns:
            Whether the simulated compile succeeded.
        """
        compiles.append(set(changed or ()))
        return len(compiles) > 1

    monkeypatch.setattr(compile_daemon, "_compile_once", compile_once)
    compile_daemon._serve()
    assert compiles == [{a, b}, {a, b}, {a}]


def test_daemon_compiles_an_edit_made_before_its_first_snapshot(tmp_path, monkeypatch):
    """An input edited after the last build but before the watch starts compiles.

    The first snapshot is the watch baseline, so such an edit raises no event.
    """
    from reflex.compiler import disk_cache, page_cache
    from reflex.utils import prerequisites

    page = tmp_path / "page.py"
    page.write_text("TITLE = 'v1'\n")
    entry = page_cache.file_entry(str(page))
    assert entry is not None
    files = {str(page): list(entry)}
    page.write_text("TITLE = 'edited before the daemon watched'\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("REFLEX_COMPILE_DAEMON_PRECOMPILED", "1")
    monkeypatch.setattr(compile_daemon, "_lock_path", lambda: tmp_path / "lock")
    monkeypatch.setattr(compile_daemon, "_reload_roots", lambda: [tmp_path])
    monkeypatch.setattr(compile_daemon, "_prepare_fork_parent", lambda roots: None)
    monkeypatch.setattr(compile_daemon, "_next_changes", lambda *args: None)
    monkeypatch.setattr(
        compile_daemon._WatchState,
        "build",
        lambda *args: compile_daemon._WatchState([tmp_path], tmp_path, known={page}),
    )
    monkeypatch.setattr(prerequisites, "get_app", lambda **kwargs: None)
    monkeypatch.setattr(disk_cache, "load_manifest", lambda: {"files": files})
    compiled = []
    monkeypatch.setattr(
        compile_daemon,
        "_compile_once",
        lambda roots, prerender, changed: compiled.append(changed) or True,
    )
    monkeypatch.setattr("reflex.utils.prerequisites.get_backend_dir", lambda: tmp_path)
    compile_daemon._serve()
    assert compiled == [{page}]
    assert compile_daemon._built_inputs_current()


def test_daemon_entry_point_runs_the_canonical_module(tmp_path):
    """``python -m`` must run the importable module, not a ``__main__`` copy.

    Records go through the ``reflex`` logger tree only from the real module's
    logger, and module state must not be split between two copies.
    """
    import subprocess

    probe = (
        "import runpy, sys\n"
        "import reflex.utils.compile_daemon as daemon\n"
        "def main(argv=None):\n"
        "    print(daemon.logger.name, sys.modules['reflex.utils.compile_daemon'] is daemon)\n"
        "    return 0\n"
        "daemon.main = main\n"
        "runpy.run_module('reflex.utils.compile_daemon', run_name='__main__')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert result.stdout.split() == ["reflex.utils.compile_daemon", "True"], (
        result.stderr
    )


def test_compile_once_retries_a_failed_prediction_exactly(monkeypatch):
    """A failed state-name prediction compiles again in a fresh child, exactly."""
    attempts = []

    def run_child(roots, prerender_routes, changed, *, predict):
        attempts.append(predict)
        return compile_daemon._RETRY_EXIT_CODE if predict else 0

    monkeypatch.setattr(compile_daemon, "_run_compile_child", run_child)
    assert compile_daemon._compile_once([], False, None) is True
    assert attempts == [True, False]


@pytest.mark.skipif(not hasattr(os, "fork"), reason="requires os.fork (POSIX)")
def test_failed_prediction_exits_the_child_with_the_retry_code(monkeypatch):
    """The forked child reports a failed prediction distinctly from a failure."""
    from reflex.compiler import disk_cache

    def fail_prediction(roots, prerender_routes, changed, predict):
        """Simulate a page claiming other state names than recorded.

        Raises:
            DynamicStatePredictionError: Always.
        """
        route = "/two"
        raise disk_cache.DynamicStatePredictionError(route)

    monkeypatch.setattr(compile_daemon, "_can_fork", lambda: True)
    monkeypatch.setattr(compile_daemon, "_child_compile", fail_prediction)
    code = compile_daemon._run_compile_child([], False, None, predict=True)
    assert code == compile_daemon._RETRY_EXIT_CODE


@pytest.mark.skipif(not hasattr(os, "fork"), reason="requires os.fork (POSIX)")
@pytest.mark.parametrize(
    ("outcome", "compiled"),
    [
        ("ok", True),
        ("fell back", False),
        ("failed prediction", False),
        ("error", False),
    ],
)
def test_cold_compile_predicts_names_in_a_child(
    monkeypatch, tmp_path, outcome, compiled
):
    """A cold compile predicts dynamic state names in a forked child.

    Only a child that compiled spares the caller its exact in-process compile.
    """
    from reflex.compiler import disk_cache

    seen = tmp_path / "predicted"

    def attempt() -> bool:
        """Record the prediction mode, then end as ``outcome`` says.

        Returns:
            Whether the compile succeeded.

        Raises:
            DynamicStatePredictionError: For a failed prediction.
            RuntimeError: For an error.
        """
        seen.write_text(str(disk_cache._predict_dynamic_names))
        if outcome == "failed prediction":
            route = "/two"
            raise disk_cache.DynamicStatePredictionError(route)
        if outcome == "error":
            msg = "boom"
            raise RuntimeError(msg)
        return outcome == "ok"

    monkeypatch.setattr(compile_daemon, "_single_threaded", lambda: True)
    assert compile_daemon.compiled_in_predicting_child(attempt) is compiled
    assert seen.read_text() == "True"
    assert disk_cache._predict_dynamic_names is None


@pytest.mark.parametrize(
    ("single_threaded", "chosen"), [(False, None), (True, False), (True, True)]
)
def test_cold_compile_without_a_safe_fork_compiles_in_process(
    monkeypatch, single_threaded, chosen
):
    """The caller compiles in-process with other threads alive or a mode chosen."""
    from reflex.compiler import disk_cache

    monkeypatch.setattr(compile_daemon, "_single_threaded", lambda: single_threaded)
    monkeypatch.setattr(disk_cache, "_predict_dynamic_names", chosen)
    assert compile_daemon.compiled_in_predicting_child(lambda: True) is False


@pytest.mark.parametrize("lock", ["held", "unsupported"])
def test_daemon_without_its_lock_does_not_serve(tmp_path, monkeypatch, lock):
    """Only the daemon holding the ownership lock compiles the project."""
    from unittest.mock import Mock

    from reflex.utils import path_ops

    lock_path = tmp_path / "daemon.lock"
    monkeypatch.setattr(compile_daemon, "_daemon_lock_path", lambda: lock_path)
    monkeypatch.setattr(compile_daemon, "_LOCK_ACQUIRE_TIMEOUT", 0.05)
    served: list[bool] = []
    monkeypatch.setattr(compile_daemon, "_serve", lambda: served.append(True))
    holder = path_ops.try_lock(lock_path) if lock == "held" else None
    if lock == "unsupported":
        monkeypatch.setattr(
            path_ops, "try_lock", Mock(side_effect=OSError(errno.ENOLCK, "no locks"))
        )
    try:
        assert compile_daemon.main([]) == 0
    finally:
        if holder is not None:
            os.close(holder)
    assert served == []


def test_built_inputs_include_dependencies_the_compile_added(tmp_path, monkeypatch):
    """Workers wait on an edit to a file the last compile started reading.

    The file was not watched before that compile, which is no edit.
    """
    from reflex.utils import prerequisites

    page, data = tmp_path / "page.py", tmp_path / "data.json"
    page.write_text("TITLE = 'v1'\n")
    data.write_text("{}")
    known = {page}
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("REFLEX_COMPILE_DAEMON_PRECOMPILED", "1")
    monkeypatch.setattr(compile_daemon, "_lock_path", lambda: tmp_path / "lock")
    monkeypatch.setattr(compile_daemon, "_reload_roots", lambda: [tmp_path])
    monkeypatch.setattr(compile_daemon, "_prepare_fork_parent", lambda roots: None)
    monkeypatch.setattr(compile_daemon, "_unbuilt_changes", lambda state: set())
    monkeypatch.setattr(prerequisites, "get_app", lambda **kwargs: None)
    monkeypatch.setattr("reflex.utils.prerequisites.get_backend_dir", lambda: tmp_path)
    monkeypatch.setattr(
        compile_daemon._WatchState,
        "build",
        lambda *args: compile_daemon._WatchState(
            [tmp_path], tmp_path, known=set(known)
        ),
    )
    batches = iter([{page}, None])
    monkeypatch.setattr(compile_daemon, "_next_changes", lambda *args: next(batches))

    def compile_once(roots, prerender_routes, changed=None) -> bool:
        """Compile a page that now reads ``data``.

        Args:
            roots: The reload roots.
            prerender_routes: Whether to prerender routes.
            changed: The changed-path hint.

        Returns:
            True.
        """
        compiles.append(changed)
        known.add(data)
        return True

    compiles: list[set[Path] | None] = []
    monkeypatch.setattr(compile_daemon, "_compile_once", compile_once)
    compile_daemon._serve()
    assert compiles == [{page}]
    assert compile_daemon._built_inputs_current()
    data.write_text('{"edited": true}')
    os.utime(data, ns=(1, 1))
    assert not compile_daemon._built_inputs_current()
