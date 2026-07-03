"""Warm compile daemon for ``REFLEX_COMPILE_CACHE`` dev hot reloads.

The daemon imports the app once, then compiles each change in an isolated child.
On POSIX it forks so third-party imports stay warm; otherwise it falls back to a
fresh subprocess. It also owns the watch loop so markdown and external content
dependencies recorded in the compile manifest trigger rebuilds.
"""

from __future__ import annotations

import contextlib
import importlib
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from reflex_base.environment import environment

from reflex.utils import console

#: Seconds between poll passes. Each pass only re-``stat``s the known file set
#: (cheap), so this can be small for snappy detection of edits to existing files.
_POLL_INTERVAL = 0.05
#: After a change is seen, wait this long and re-snapshot so a burst of saves
#: (e.g. format-on-save touching many files) collapses into a single compile.
_DEBOUNCE = 0.05
#: How often to re-walk the tree to discover added/removed files.
#: Between rescans we only ``stat`` the known set; adds are rarer and tolerate a
#: little latency, so this keeps idle CPU low while polling fast for edits.
_RESCAN_INTERVAL = 1.0
#: Watchdog: kill a compile child that runs longer than this (a hung/deadlocked
#: child must never wedge the daemon). Generous enough for a real full compile.
_COMPILE_TIMEOUT = 300.0
#: Source suffixes edited under the app roots that should trigger a recompile.
_WATCH_SUFFIXES = (".py", ".md", ".mdx")
#: Directories never worth walking while building the watch snapshot.
_SKIP_DIRS = {".web", ".venv", "venv", "node_modules", "__pycache__", ".git"}


def run_compile_daemon(prerender_routes: bool = False) -> None:
    """Supervise the compile daemon as its own (fork-safe) subprocess.

    Runs on a ``reflex run`` worker thread alongside the frontend. Launching the
    daemon as a separate process keeps it single-threaded so its per-edit
    ``fork()`` is safe, and isolates its environment from the backend (which is
    told to skip frontend compilation via ``REFLEX_SKIP_COMPILE``).

    Args:
        prerender_routes: Whether the daemon should prerender routes when compiling.
    """
    env = {**os.environ}
    # The daemon DOES compile; ensure the cache is on and the skip flag is off.
    env.pop(environment.REFLEX_SKIP_COMPILE.name, None)
    env[environment.REFLEX_COMPILE_CACHE.name] = "1"
    if prerender_routes:
        env["REFLEX_PRERENDER_ROUTES"] = "1"
    proc = subprocess.Popen(
        [sys.executable, "-m", "reflex.utils.compile_daemon"], env=env
    )

    def _terminate() -> None:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()

    # Backstop: the daemon must never outlive reflex-run, even if this thread is
    # interrupted before its finally runs. The daemon also self-exits if its
    # parent dies (see _serve), so the two together prevent an orphan.
    import atexit

    atexit.register(_terminate)
    try:
        proc.wait()
    finally:
        _terminate()


def _reload_roots() -> list[Path]:
    """Resolve the directories/files that hold the user's first-party source.

    Returns:
        The resolved reload roots (the same set the backend reloader watches).
    """
    from reflex.utils import exec as exec_utils

    return [Path(p).resolve() for p in exec_utils.get_reload_paths()]


def _under_roots(path: Path, roots: list[Path]) -> bool:
    """Whether ``path`` is one of, or lives under, the reload roots.

    Args:
        path: The resolved path to test.
        roots: The resolved reload roots.

    Returns:
        True if the path is covered by a reload root.
    """
    return any(path == root or root in path.parents for root in roots)


def _iter_source_files(root: Path):
    """Yield watchable source files under ``root`` (skipping build/dep dirs).

    Args:
        root: A reload root directory (or file).

    Yields:
        Resolved source file paths with a watched suffix.
    """
    if root.is_file():
        if root.suffix in _WATCH_SUFFIXES:
            yield root.resolve()
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            name
            for name in dirnames
            if name not in _SKIP_DIRS and not name.startswith(".")
        ]
        base = Path(dirpath)
        for name in filenames:
            path = base / name
            if path.suffix in _WATCH_SUFFIXES:
                yield path.resolve()


def _external_dependency_files(roots: list[Path]) -> set[Path]:
    """External content files the compiler read, taken from the disk manifest.

    The manifest records each page's full dependency set (own module, markdown,
    component/state modules). Any dependency that lives *outside* the reload
    roots, such as a docs app's markdown in a sibling directory, is invisible to
    ``get_reload_paths`` and must be watched explicitly so editing it rebuilds.

    Args:
        roots: The resolved reload roots.

    Returns:
        Resolved external dependency file paths to watch.
    """
    from reflex.compiler import disk_cache

    manifest = disk_cache.load_manifest()
    if not manifest:
        return set()
    out: set[Path] = set()
    for page in manifest.get("pages", {}).values():
        for dep in page.get("dep_hashes", {}):
            path = Path(dep)
            if not _under_roots(path, roots):
                out.add(path)
    return out


def _global_files(root: Path) -> set[Path]:
    """Genuinely-global files whose change forces a full rebuild / daemon restart.

    Args:
        root: The project root.

    Returns:
        Resolved paths of rxconfig + lockfiles + package.json that exist.
    """
    from reflex.compiler import page_cache

    return {
        (root / name).resolve()
        for name in page_cache._GLOBAL_FILES
        if (root / name).exists()
    }


def _mtime_ns(path: Path) -> int | None:
    """Return the file's modification time in ns, or None if it can't be read.

    Args:
        path: The file to stat.

    Returns:
        The ``st_mtime_ns`` value, or None on error.
    """
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return None


def _watch_paths(roots: list[Path], root: Path, external_files: set[Path]) -> set[Path]:
    """Build the full set of files to watch this tick.

    ``external_files`` (the per-page external content deps from the manifest) is
    passed in rather than re-read here, so the manifest is parsed once per compile
    instead of on every poll tick.

    Args:
        roots: The resolved reload roots.
        root: The project root.
        external_files: External content dependency files (from the manifest).

    Returns:
        The set of paths to snapshot.
    """
    paths: set[Path] = set(external_files)
    for r in roots:
        paths.update(_iter_source_files(r))
    paths.update(_global_files(root))
    assets = root / "assets"
    if assets.is_dir():
        paths.update(p.resolve() for p in assets.rglob("*") if p.is_file())
    return paths


def _snapshot(paths: set[Path]) -> dict[Path, int]:
    """Snapshot ``{path: mtime_ns}`` for the given files.

    Args:
        paths: The files to stat.

    Returns:
        A mapping of file path to its modification time (unreadable files omitted).
    """
    return {p: m for p in paths if (m := _mtime_ns(p)) is not None}


def _first_party_module_names(roots: list[Path]) -> set[str]:
    """Names of all loaded modules belonging to the user's first-party packages.

    First-party top-level package names are inferred from the *regular* modules
    whose ``__file__`` resolves under a reload root (a plain attribute read, no
    namespace-package ``__path__`` recalculation, which is lazy and would break
    while ``sys.modules`` is being mutated). Every loaded module sharing one of
    those top-level names is then first-party, which captures namespace packages
    (they have no ``__file__``) purely by name string.

    Args:
        roots: The resolved reload roots.

    Returns:
        The set of ``sys.modules`` keys to purge.
    """
    top_level: set[str] = set()
    for name, mod in list(sys.modules.items()):
        file = getattr(mod, "__file__", None)
        if not file:
            continue
        try:
            rf = Path(file).resolve()
        except OSError:
            continue
        if _under_roots(rf, roots):
            top_level.add(name.partition(".")[0])
    if not top_level:
        return set()
    return {name for name in sys.modules if name.partition(".")[0] in top_level}


def _reset_first_party(roots: list[Path]) -> None:
    """Make this interpreter clean w.r.t. first-party code before re-importing.

    Purges the user's first-party modules from ``sys.modules`` and resets the
    cross-module registries/caches that would otherwise pin old class objects.
    Third-party modules are left imported and warm.

    The state registry is reset surgically, not blanket-cleared: a class body
    in a module that survives the purge (framework internals, installed or
    workspace packages) never re-executes in this process, so clearing its
    registration would lose the state from the app's state tree — and from the
    compiled contexts file — permanently. Those registrations are kept; states
    from purged modules re-register on re-import, and runtime-created states in
    ``reflex.istate.dynamic`` re-register when their page re-evaluates.

    Args:
        roots: The resolved reload roots whose modules are first-party.
    """
    for name in _first_party_module_names(roots):
        sys.modules.pop(name, None)
    # The import-system finder caches were inherited from the warm parent via
    # fork and are now stale (they reference the purged modules); without this a
    # re-import can resolve a stale spec for a since-changed module.
    importlib.invalidate_caches()

    from reflex_base.registry import RegistrationContext

    import reflex.istate.dynamic as istate_dynamic
    from reflex.compiler import page_cache
    from reflex.page import DECORATED_PAGES
    from reflex.state import BaseState, all_base_state_classes

    ctx = RegistrationContext.ensure_context()
    kept = [
        cls
        for cls in ctx.base_states.values()
        if (module_name := getattr(cls, "__module__", None)) is not None
        and module_name != istate_dynamic.__name__
        and getattr(sys.modules.get(module_name), "__file__", None) is not None
    ]
    ctx.base_states.clear()
    ctx.base_state_substates.clear()
    ctx.event_handlers.clear()
    all_base_state_classes.clear()
    for cached in (
        BaseState.get_parent_state,
        BaseState.get_root_state,
        BaseState.get_name,
        BaseState.get_full_name,
        BaseState.get_class_substate,
    ):
        cached.cache_clear()
    # Locally-defined states are attached to ``reflex.istate.dynamic`` under
    # collision-suffixed names; with the warm parent's attributes in place,
    # every re-created state would drift to a new suffix and diverge from the
    # names the (cold) backend computes. Reset the module so re-created states
    # get their fresh-process names.
    for attr in [name for name in vars(istate_dynamic) if not name.startswith("__")]:
        delattr(istate_dynamic, attr)
    # Original registration order, so parents always precede their children.
    for cls in kept:
        ctx._register_base_state(cls)
        all_base_state_classes[cls.get_full_name()] = None
    DECORATED_PAGES.clear()
    # The import graph caches each module's parsed import edges; a changed file
    # may import differently now, so drop it to force a re-parse. Cross-compile
    # page reuse comes from the on-disk manifest.
    page_cache.clear_import_graph()
    _reset_model_metadata()


def _reset_model_metadata() -> None:
    """Clear the SQLAlchemy/SQLModel table + model registries.

    ``rx.Model`` subclasses (including ones a docs demo ``exec``s) register their
    table in a process-global ``MetaData`` that lives in the framework, which the
    forked child inherits warm and populated. Re-evaluating a page that defines
    such a model would then raise ``Table '...' is already defined``. A fresh
    respawn never hits this (empty registry); resetting here restores that
    fresh-process contract. Best-effort: apps without a DB layer have nothing to
    clear.
    """
    with contextlib.suppress(Exception):
        import sqlmodel

        sqlmodel.SQLModel.metadata.clear()
    with contextlib.suppress(Exception):
        from reflex.model import Model

        Model.metadata.clear()
    with contextlib.suppress(Exception):
        from reflex.model import ModelRegistry

        ModelRegistry.models.clear()
        ModelRegistry._metadata = None


def _child_compile(roots: list[Path], prerender_routes: bool) -> None:
    """Reset first-party state, re-import the app fresh, and compile incrementally.

    Runs in a forked child (POSIX) or a one-shot subprocess (Windows). Must not
    return normally on error; the caller maps the exit code to success/failure.

    Args:
        roots: The resolved reload roots.
        prerender_routes: Whether to prerender routes during compile.
    """
    from reflex.utils import prerequisites

    # Timed in three steps so every hot reload reports where it spent its time
    # (resetting state vs re-importing first-party code vs compiling).
    t0 = time.perf_counter()
    _reset_first_party(roots)
    t1 = time.perf_counter()
    app, _ = prerequisites.get_and_validate_app(reload=False)
    t2 = time.perf_counter()
    app._compile(prerender_routes=prerender_routes, use_rich=True, trigger="hot_reload")
    t3 = time.perf_counter()
    console.info(
        f"Hot reload {t3 - t0:.2f}s (reset {t1 - t0:.2f}s, "
        f"reimport {t2 - t1:.2f}s, compile {t3 - t2:.2f}s)"
    )


def _await_child(pid: int) -> bool:
    """Reap a forked compile child, killing it if it exceeds the watchdog timeout.

    Args:
        pid: The forked child's pid.

    Returns:
        True if it exited 0; False on failure, timeout, or signal (a
        signal-killed child, such as Ctrl-C during shutdown, is a quiet False).
    """
    deadline = time.monotonic() + _COMPILE_TIMEOUT
    while True:
        done, status = os.waitpid(pid, os.WNOHANG)
        if done == pid:
            return os.waitstatus_to_exitcode(status) == 0
        if time.monotonic() > deadline:
            with contextlib.suppress(OSError):
                os.kill(pid, signal.SIGKILL)
            with contextlib.suppress(OSError):
                os.waitpid(pid, 0)
            console.error("Compile child timed out; killed it, keeping last build.")
            return False
        time.sleep(0.02)


def _can_fork() -> bool:
    """Whether forking is safe right now (POSIX and the process is single-threaded).

    Forking a multi-threaded process and then running Python (not exec) inherits
    locks held by threads that don't exist in the child. The
    user app, imported warm in the parent, may have started a background thread
    at import time, so this is checked per compile.

    Returns:
        True if a per-compile ``fork()`` is safe.
    """
    return hasattr(os, "fork") and threading.active_count() == 1


def _compile_once(roots: list[Path], prerender_routes: bool) -> bool:
    """Run one incremental compile in an isolated child; report success.

    Uses a copy-on-write ``fork()`` when safe (warm), else a fresh subprocess
    (Windows, or when the warm parent is no longer single-threaded).

    Args:
        roots: The resolved reload roots.
        prerender_routes: Whether to prerender routes during compile.

    Returns:
        True if the child compiled successfully, else False.
    """
    if _can_fork():
        pid = os.fork()
        if pid == 0:  # child
            code = 0
            try:
                _child_compile(roots, prerender_routes)
            except BaseException:  # report any failure, never crash the daemon
                import traceback

                traceback.print_exc()
                code = 1
            finally:
                os._exit(code)
        return _await_child(pid)

    # No fork (Windows) or unsafe to fork: a fresh (cold) subprocess compiles.
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "reflex.utils.compile_daemon", "--once"],
            check=False,
            timeout=_COMPILE_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        console.error("Compile subprocess timed out; keeping the last good build.")
        return False
    return proc.returncode == 0


def _serve() -> None:
    """Run the warm compile daemon: initial compile, then watch-and-recompile."""
    from reflex.utils import prerequisites

    root = Path.cwd()
    prerender_routes = bool(os.environ.get("REFLEX_PRERENDER_ROUTES"))
    roots = _reload_roots()
    parent_pid = os.getppid()

    # Warm import + initial compile (writes .web + the manifest); keeps the app
    # and its third-party deps resident for copy-on-write children. A failure
    # here (e.g. the app is mid-edit and broken) must NOT kill the daemon; fall
    # through to the watch loop so the next edit that fixes it recompiles.
    try:
        with console.timing("Compile daemon: initial compile"):
            prerequisites.get_compiled_app(
                reload=False,
                prerender_routes=prerender_routes,
                use_rich=True,
                trigger="initial",
            )
    except BaseException:  # tolerate a broken initial state; keep watching
        import traceback

        traceback.print_exc()
        console.error("Initial compile failed; watching for a fix.")

    # External content deps (e.g. a docs app's sibling-dir markdown) come from
    # the manifest; recompute only after a compile, not on every poll tick.
    external = _external_dependency_files(roots)
    global_files = _global_files(root)
    # `paths` is the watched set, refreshed by a tree rescan; each tick only
    # re-stats it (cheap), so the poll can be fast without burning idle CPU.
    paths = _watch_paths(roots, root, external)
    snapshot = _snapshot(paths)
    last_rescan = time.monotonic()
    console.info("Compile daemon ready (warm); watching for changes.")

    while True:
        time.sleep(_POLL_INTERVAL)
        # Never outlive reflex-run: if our parent died we were reparented.
        if os.getppid() != parent_pid:
            return
        # Cheap stat of the known set every tick; re-walk the tree occasionally
        # to discover added/removed files.
        if time.monotonic() - last_rescan >= _RESCAN_INTERVAL:
            paths = _watch_paths(roots, root, external)
            last_rescan = time.monotonic()
        current = _snapshot(paths)
        changed = {
            p
            for p in current.keys() | snapshot.keys()
            if current.get(p) != snapshot.get(p)
        }
        if not changed:
            continue

        from reflex.compiler.disk_cache import format_path_list

        console.info(
            f"Compile daemon: change detected in {format_path_list(map(str, changed), root)}"
        )

        # A change to a genuinely-global input (rxconfig/lockfiles, or a reflex
        # upgrade) can't be applied to the warm parent (it imported the old
        # version); re-exec the daemon so the new world is actually loaded.
        if changed & global_files:
            console.info("Global config changed; restarting compile daemon.")
            os.execv(
                sys.executable, [sys.executable, "-m", "reflex.utils.compile_daemon"]
            )

        time.sleep(_DEBOUNCE)  # absorb the rest of a burst of saves
        roots = _reload_roots()
        ok = _compile_once(roots, prerender_routes)
        if not ok:
            console.error("Compile failed; keeping the last good build.")
        # Re-snapshot AFTER compiling so writes the compile itself made are the
        # new baseline; refresh external deps + globals from the new manifest so
        # a newly-referenced content dir becomes watched.
        external = _external_dependency_files(roots)
        global_files = _global_files(root)
        paths = _watch_paths(roots, root, external)
        snapshot = _snapshot(paths)
        last_rescan = time.monotonic()


def main(argv: list[str] | None = None) -> int:
    """Entry point for ``python -m reflex.utils.compile_daemon``.

    Args:
        argv: Command-line arguments (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code.
    """
    argv = sys.argv[1:] if argv is None else argv
    if "--once" in argv:
        try:
            _child_compile(
                _reload_roots(), bool(os.environ.get("REFLEX_PRERENDER_ROUTES"))
            )
        except BaseException:  # report any failure, never crash
            import traceback

            traceback.print_exc()
            return 1
        return 0
    try:
        _serve()
    except KeyboardInterrupt:
        return 0  # clean shutdown (Ctrl-C); no traceback
    return 0


if __name__ == "__main__":
    sys.exit(main())
