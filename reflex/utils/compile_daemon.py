"""Warm compile daemon for ``REFLEX_COMPILE_CACHE`` dev hot reloads.

The daemon imports the app once, then compiles each change in an isolated child.
On POSIX it forks so third-party imports stay warm; otherwise it falls back to a
fresh subprocess. It also owns the watch loop so markdown and external content
dependencies recorded in the compile manifest trigger rebuilds.
"""

from __future__ import annotations

import contextlib
import importlib
import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from reflex_base import constants
from reflex_base.environment import environment
from reflex_base.utils import log

from reflex.utils import path_ops

if TYPE_CHECKING:
    from reflex.compiler import page_cache

logger = logging.getLogger(__name__)

#: Fallback polling only (no ``watchfiles``): seconds between poll passes.
_POLL_INTERVAL = 0.5
#: Milliseconds a burst of saves (e.g. format-on-save touching many files) is
#: allowed to settle before it is reported as one change set.
_DEBOUNCE_MS = 50
#: How long the OS watcher blocks before yielding control back, so the daemon
#: can notice its parent died even while no file changes.
_WATCH_TIMEOUT_MS = 1000
#: Fallback polling only: how often to re-walk the tree for added files.
_RESCAN_INTERVAL = 1.0
#: Watchdog: kill a compile child that runs longer than this (a hung/deadlocked
#: child must never wedge the daemon). Generous enough for a real full compile.
_COMPILE_TIMEOUT = 300.0
#: Source suffixes edited under the app roots that should trigger a recompile.
_WATCH_SUFFIXES = (".py", ".md", ".mdx")
#: Directories never worth walking while building the watch snapshot.
_SKIP_DIRS = {
    constants.Dirs.WEB,
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".git",
}


@contextlib.contextmanager
def running(
    prerender_routes: bool = False, initial_compiled: bool = False
) -> Iterator[None]:
    """Run the compile daemon as a subprocess for the duration of the block.

    ``reflex run`` owns the daemon's lifetime: however the block exits (Ctrl-C,
    a signal to ``reflex run`` alone, an error), the daemon is stopped, which
    releases its lock, so backend workers compile again. The daemon is
    its own process so that it stays single-threaded, which keeps its per-edit
    ``fork()`` safe, and its environment stays separate from the backend's. If
    ``reflex run`` is killed outright, the daemon exits on noticing its parent
    is gone (see :func:`_serve`).

    Args:
        prerender_routes: Whether the daemon should prerender routes when compiling.
        initial_compiled: Whether the parent already produced the initial frontend.

    Yields:
        None, while the daemon runs.
    """
    env = {**os.environ}
    # The daemon DOES compile; ensure the cache is on and the skip flag is off.
    env.pop(environment.REFLEX_SKIP_COMPILE.name, None)
    env[environment.REFLEX_COMPILE_CACHE.name] = "1"
    env[environment.REFLEX_COMPILE_DAEMON.name] = "1"
    if prerender_routes:
        env["REFLEX_PRERENDER_ROUTES"] = "1"
    if initial_compiled:
        env["REFLEX_COMPILE_DAEMON_PRECOMPILED"] = "1"
    proc = subprocess.Popen(
        [sys.executable, "-m", "reflex.utils.compile_daemon"], env=env
    )
    try:
        yield
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


def _reload_roots() -> list[Path]:
    """Resolve the directories/files that hold the user's first-party source.

    Returns:
        The resolved reload roots (the same set the backend reloader watches).
    """
    from reflex.utils import exec as exec_utils

    return [Path(p).resolve() for p in exec_utils.get_reload_paths()]


def _under_roots(path: Path, roots: list[Path]) -> bool:
    """Whether ``path`` is one of, or lives under, the reload roots.

    Compares path strings: this runs for every loaded module on every hot
    reload, and ``root in path.parents`` constructs a Path object per ancestor
    per check, which dominated the reset phase of a reload.

    Args:
        path: The resolved path to test.
        roots: The resolved reload roots.

    Returns:
        True if the path is covered by a reload root.
    """
    path_str = str(path)
    for root in roots:
        root_str = str(root)
        if path_str == root_str or path_str.startswith(
            root_str if root_str.endswith(os.sep) else root_str + os.sep
        ):
            return True
    return False


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


def _manifest_dependency_files() -> set[Path]:
    """Every source dependency the last compile recorded, from the disk manifest.

    Returns:
        Resolved dependency file paths (empty without a manifest).
    """
    from reflex.compiler import disk_cache

    manifest = disk_cache.load_manifest()
    if not manifest:
        return set()
    return {Path(dep) for dep in disk_cache.manifest_dependency_files(manifest)}


def _external_dependency_files(roots: list[Path]) -> set[Path]:
    """Recorded dependencies that live *outside* the reload roots.

    Such files (a docs app's markdown in a sibling directory, say) are invisible
    to ``get_reload_paths`` and must be watched explicitly so editing them
    rebuilds.

    Args:
        roots: The resolved reload roots.

    Returns:
        Resolved external dependency file paths to watch.
    """
    return {p for p in _manifest_dependency_files() if not _under_roots(p, roots)}


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


@dataclass
class _WatchState:
    """What the daemon watches; refreshed after every compile."""

    roots: list[Path]
    root: Path
    #: Every dependency the last compile recorded (any suffix), so an edit to a
    #: JSON/CSV/etc. file a page reads triggers a rebuild too.
    known: set[Path] = field(default_factory=set)
    globals_: set[Path] = field(default_factory=set)
    #: Last post-compile snapshot, reconciled once the watcher subscribes again.
    checkpoint: dict[Path, int] | None = None

    @classmethod
    def build(cls, roots: list[Path], root: Path) -> _WatchState:
        """Snapshot the current watch inputs from the manifest and roots.

        Args:
            roots: The resolved reload roots.
            root: The project root.

        Returns:
            The populated watch state.
        """
        return cls(
            roots=roots,
            root=root,
            known=_manifest_dependency_files(),
            globals_=_global_files(root),
        )

    @property
    def assets(self) -> Path | None:
        """The assets directory, when the project has one."""
        assets = self.root / constants.Dirs.APP_ASSETS
        return assets if assets.is_dir() else None

    def targets(self) -> list[Path]:
        """Directories/files handed to the OS watcher.

        Returns:
            The reload roots, the parents of recorded dependencies outside
            them, the project root's global files and the assets directory.
        """
        targets: dict[Path, None] = dict.fromkeys([self.root, *self.roots])
        for dep in self.known:
            if not _under_roots(dep, self.roots):
                targets[dep.parent] = None
        for path in self.globals_:
            targets[path] = None
        if (assets := self.assets) is not None:
            targets[assets] = None
        return [t for t in targets if t.exists()]

    def accepts(self, path: Path) -> bool:
        """Whether a changed path is a compile input worth reacting to.

        Args:
            path: The changed path, as reported by the watcher.

        Returns:
            True for watched-suffix sources, recorded dependencies, global
            inputs and assets; False for build output and unrelated files.
        """
        if any(part in _SKIP_DIRS for part in path.parts):
            return False
        if path in self.globals_ or path in self.known:
            return True
        if (assets := self.assets) is not None and _under_roots(path, [assets]):
            return True
        return path.suffix in _WATCH_SUFFIXES and (
            path.parent == self.root or _under_roots(path, self.roots)
        )

    def watch_paths(self) -> set[Path]:
        """Collect inputs for polling and watch-subscription catch-up snapshots.

        Returns:
            The set of paths to stat.
        """
        paths: set[Path] = set(self.known)
        for r in self.roots:
            paths.update(_iter_source_files(r))
        paths.update(
            p
            for p in self.root.iterdir()
            if p.is_file() and p.suffix in _WATCH_SUFFIXES
        )
        paths.update(self.globals_)
        if (assets := self.assets) is not None:
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


def _poll_changes(state: _WatchState, alive: Callable[[], bool]) -> set[Path] | None:
    """Fallback change source when ``watchfiles`` is unavailable.

    Re-stats the known file set every ``_POLL_INTERVAL`` and re-walks the tree
    every ``_RESCAN_INTERVAL`` to discover added files.

    Args:
        state: The live watch state.
        alive: Returns False when the watcher should stop.

    Returns:
        The first non-empty set of changed paths, or None once ``alive`` is
        False.
    """
    paths = state.watch_paths()
    snapshot = _snapshot(paths)
    if state.checkpoint is not None and (
        changed := _missed_changes(state.checkpoint, snapshot)
    ):
        state.checkpoint = snapshot
        return changed
    state.checkpoint = snapshot
    last_rescan = time.monotonic()
    while alive():
        time.sleep(_POLL_INTERVAL)
        if time.monotonic() - last_rescan >= _RESCAN_INTERVAL:
            paths = state.watch_paths()
            last_rescan = time.monotonic()
        current = _snapshot(paths)
        changed = {
            p
            for p in current.keys() | snapshot.keys()
            if current.get(p) != snapshot.get(p)
        }
        state.checkpoint = current
        if changed:
            time.sleep(_DEBOUNCE_MS / 1000)  # absorb the rest of a burst
            return changed
        snapshot = current
    return None


def _next_changes(state: _WatchState, alive: Callable[[], bool]) -> set[Path] | None:
    """Block until compile inputs change; return the changed paths.

    Subscribes to filesystem notifications (``watchfiles``: inotify, FSEvents,
    ReadDirectoryChangesW) over ``state.targets()``, filtered by
    ``state.accepts``. Polling is only a fallback when ``watchfiles`` is not
    importable.

    The watcher is torn down before returning: it runs a native thread, and
    the compile that follows forks the (otherwise single-threaded) daemon.
    Edits made while the watcher is down are caught up by
    :func:`_missed_changes` after the compile.

    Args:
        state: The live watch state.
        alive: Returns False when the watcher should stop.

    Returns:
        A non-empty set of changed paths, or None once ``alive`` is False.
    """
    try:
        import watchfiles
    except ImportError:
        logger.warning(
            "watchfiles is not installed; the compile daemon falls back to polling."
        )
        return _poll_changes(state, alive)

    def watch_filter(_change: object, raw_path: str) -> bool:
        return state.accepts(Path(raw_path))

    events = watchfiles.watch(
        *state.targets(),
        watch_filter=watch_filter,
        debounce=_DEBOUNCE_MS,
        step=25,
        rust_timeout=_WATCH_TIMEOUT_MS,
        yield_on_timeout=True,
        raise_interrupt=False,
    )
    checkpoint = state.checkpoint
    try:
        for batch in events:
            if not alive():
                return None
            changed = {Path(raw_path) for _change, raw_path in batch}
            if changed or checkpoint is not None:
                current = _dependency_snapshot(state)
                if state.checkpoint is not None:
                    changed.update(_missed_changes(state.checkpoint, current))
                state.checkpoint = current
                checkpoint = None
            if changed:
                return changed
    finally:
        events.close()  # stops the native watcher thread before any fork
    return None


def _dependency_snapshot(state: _WatchState) -> dict[Path, int]:
    """Snapshot all watchable inputs while the OS watcher is stopped.

    Args:
        state: The watch state whose known dependencies to stat.

    Returns:
        ``{path: mtime_ns}`` for every readable watched input.
    """
    return _snapshot(state.watch_paths())


def _known_snapshot(state: _WatchState, snapshot: dict[Path, int]) -> dict[Path, int]:
    """Restrict a snapshot to recorded compile inputs.

    Only their edits are sure to trigger a compile; a backend worker waiting on
    any other file could wait for a build that never comes.

    Args:
        state: The watch state the snapshot was taken for.
        snapshot: ``{path: mtime_ns}`` of the watched inputs.

    Returns:
        The entries of ``snapshot`` for ``state.known``.
    """
    return {p: m for p, m in snapshot.items() if p in state.known}


def _recorded_inputs(
    paths: Iterable[Path],
) -> tuple[page_cache.FileValidator, dict[Path, list[str]]] | None:
    """Find the manifest entries of input files.

    A file is recorded whole, as function slices (``<file>::<function>``),
    or both.

    Args:
        paths: The input files.

    Returns:
        A validator for the manifest's file table and each recorded file's
        entries, or None without a manifest.
    """
    from reflex.compiler import disk_cache, page_cache

    if (manifest := disk_cache.load_manifest()) is None:
        return None
    files = manifest["files"]
    wanted = {str(path): path for path in paths}
    entries: dict[Path, list[str]] = {}
    for key in files:
        if (path := wanted.get(page_cache.dep_file(key))) is not None:
            entries.setdefault(path, []).append(key)
    return page_cache.FileValidator(files), entries


def _unbuilt_changes(state: _WatchState) -> set[Path]:
    """Recorded compile inputs that differ from the manifest on disk.

    Args:
        state: The current watch state.

    Returns:
        The inputs edited since the last build wrote its manifest.
    """
    if (recorded := _recorded_inputs(state.known)) is None:
        return set()
    validator, entries = recorded
    return {path for path, keys in entries.items() if not validator.unchanged(keys)}


def _built_inputs(paths: set[Path]) -> set[Path]:
    """Inputs the manifest records with their current content.

    Args:
        paths: The input files.

    Returns:
        The paths that have entries, all unchanged.
    """
    if (recorded := _recorded_inputs(paths)) is None:
        return set()
    validator, entries = recorded
    return {path for path, keys in entries.items() if validator.unchanged(keys)}


def _missed_changes(before: dict[Path, int], after: dict[Path, int]) -> set[Path]:
    """Inputs that changed between two dependency snapshots.

    Args:
        before: Snapshot taken before the watcher was torn down.
        after: Snapshot taken once it is about to be re-armed.

    Returns:
        The paths whose mtime differs (or that appeared/disappeared).
    """
    return {p for p in before.keys() | after.keys() if before.get(p) != after.get(p)}


#: ``__file__`` -> whether it is under the reload roots; the "" key holds the
#: roots the cache was built for.
_first_party_file_cache: dict[str, object] = {}


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
    roots_key = tuple(str(r) for r in roots)
    if _first_party_file_cache.get("") != roots_key:
        _first_party_file_cache.clear()
        _first_party_file_cache[""] = roots_key
    top_level: set[str] = set()
    for name, mod in list(sys.modules.items()):
        file = getattr(mod, "__file__", None)
        if not file:
            continue
        # Resolving every loaded module's file is thousands of realpath
        # syscalls per hot reload; module files never move, so classify each
        # ``__file__`` once. The parent warms this before forking.
        is_first_party = _first_party_file_cache.get(file)
        if is_first_party is None:
            try:
                is_first_party = _under_roots(Path(file).resolve(), roots)
            except OSError:
                is_first_party = False
            _first_party_file_cache[file] = is_first_party
        if is_first_party:
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
    from reflex.state import BaseState, _frontend_schema, all_base_state_classes

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
    # Kept classes' per-class caches stay valid; these caches span the tree.
    BaseState.get_class_substate.cache_clear()
    _frontend_schema.cache_clear()
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
    ctx.decorated_pages.clear()
    object.__setattr__(ctx, "_app", None)
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
    fresh-process contract. Only a loaded model layer holds tables; one a page
    imports first starts empty, as in a fresh process.
    """
    if (sqlmodel := sys.modules.get("sqlmodel")) is not None:
        sqlmodel.SQLModel.metadata.clear()
    if (model := sys.modules.get("reflex.model")) is None:
        return
    # Without the DB extras these are stubs that have no registries.
    with contextlib.suppress(AttributeError):
        model.Model.metadata.clear()
    with contextlib.suppress(AttributeError):
        model.ModelRegistry.models.clear()
        model.ModelRegistry._metadata = None


#: Name of the env var carrying the changed-path hint to a cold compile child.
_CHANGED_ENV = "REFLEX_COMPILE_CHANGED"
#: Name of the env var telling a cold compile child to predict dynamic state names.
_PREDICT_ENV = "REFLEX_COMPILE_PREDICT_DYNAMIC_NAMES"
#: Exit code of a compile child whose dynamic state name prediction failed; the
#: daemon compiles again in a fresh child without prediction.
_RETRY_EXIT_CODE = 3
#: Lock file (under the backend dir) whose OS lock the daemon holds while a
#: compile is in progress, so a backend reload worker can wait for the fresh
#: stateful-pages marker.
_COMPILE_LOCK_FILE = ".compile_in_progress"
#: Give up waiting on the lock after this long (a wedged daemon must not hang
#: the backend forever; its own watchdog is ``_COMPILE_TIMEOUT``).
_LOCK_WAIT_TIMEOUT = _COMPILE_TIMEOUT + 10
#: File (under the backend dir) holding ``{path: mtime_ns}`` of the compile
#: inputs the frontend build reflects, so a backend reload worker can tell an
#: edit the daemon has not compiled yet from one it has.
_BUILT_INPUTS_FILE = ".compiled_inputs.json"
#: Briefly retry Windows readers that prevent atomically replacing the record.
_BUILT_INPUTS_WRITE_ATTEMPTS = 3
_BUILT_INPUTS_RETRY_DELAY = 0.01
#: Lock file (under the backend dir) whose OS lock the daemon holds for its
#: lifetime. Backend workers skip frontend compilation while it is held. A
#: file, not an environment variable: workers may be forked from a
#: ``forkserver`` whose environment predates ``reflex run`` deciding to start
#: the daemon.
_DAEMON_LOCK_FILE = ".compile_daemon"
#: How long a lock holder waits out a worker's momentary probe of the lock.
_LOCK_ACQUIRE_TIMEOUT = 1.0


def _lock_path() -> Path:
    """Return the compile-in-progress lock file.

    Returns:
        The lock file under the backend dir.
    """
    from reflex.utils import prerequisites

    return prerequisites.get_backend_dir() / _COMPILE_LOCK_FILE


def _daemon_lock_path() -> Path:
    """Return the daemon ownership lock file.

    Returns:
        The lock file under the backend dir.
    """
    from reflex.utils import prerequisites

    return prerequisites.get_backend_dir() / _DAEMON_LOCK_FILE


def _acquire_lock(path: Path) -> int | None:
    """Take the OS lock on ``path``, waiting out other processes' probes of it.

    Args:
        path: The lock file.

    Returns:
        The descriptor holding the lock, or None when another process keeps it.
    """
    deadline = time.monotonic() + _LOCK_ACQUIRE_TIMEOUT
    while (descriptor := path_ops.try_lock(path)) is None:
        if time.monotonic() > deadline:
            return None
        time.sleep(0.005)
    return descriptor


def daemon_active() -> bool:
    """Whether a live compile daemon owns frontend compilation.

    Returns:
        True while a daemon holds its lock.
    """
    return path_ops.is_locked(_daemon_lock_path())


def owns_compilation() -> bool:
    """Whether this process should produce ``.web`` itself.

    False for a backend reload worker while a compile daemon owns the build;
    the daemon (and its forked compile children) carry
    ``REFLEX_COMPILE_DAEMON`` and always own it. Decided from the on-disk
    lock rather than inherited environment, which a ``forkserver`` started
    before ``reflex run`` chose the daemon would not carry.

    Returns:
        True if this process compiles the frontend.
    """
    return environment.REFLEX_COMPILE_DAEMON.get() or not daemon_active()


@contextlib.contextmanager
def _compile_lock(root: Path):
    """Hold the compile-in-progress lock while a hot-reload compile runs.

    The backend's reload worker reacts to the same file save as the daemon.
    Without this it can restart, read the previous ``stateful_pages`` marker
    and register the old state set before the daemon has rewritten it (see
    :func:`wait_for_compile`).

    Args:
        root: The project root.

    Yields:
        None.
    """
    descriptor = _acquire_lock(_lock_path())
    try:
        yield
    finally:
        # Closing releases the lock; the file stays so every holder and
        # waiter uses the same inode.
        if descriptor is not None:
            os.close(descriptor)


def _built_inputs_path() -> Path:
    """The built-inputs record under the backend dir.

    Returns:
        The record's path.
    """
    from reflex.utils import prerequisites

    return prerequisites.get_backend_dir() / _BUILT_INPUTS_FILE


def _record_built_inputs(snapshot: dict[Path, int]) -> None:
    """Record the compile inputs the frontend build now reflects.

    Args:
        snapshot: ``{path: mtime_ns}`` of the inputs the compile read.
    """
    path = _built_inputs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(json.dumps({str(p): m for p, m in snapshot.items()}))
        for attempt in range(_BUILT_INPUTS_WRITE_ATTEMPTS):
            try:
                tmp.replace(path)
            except PermissionError:
                if (
                    not constants.IS_WINDOWS
                    or attempt == _BUILT_INPUTS_WRITE_ATTEMPTS - 1
                ):
                    raise
                time.sleep(_BUILT_INPUTS_RETRY_DELAY * (attempt + 1))
            else:
                return
    finally:
        tmp.unlink(missing_ok=True)


def _built_inputs_current() -> bool:
    """Whether every recorded compile input still has its built mtime.

    Returns:
        True when the build reflects the inputs (or nothing was recorded).
    """
    try:
        built = json.loads(_built_inputs_path().read_text())
    except FileNotFoundError:
        return True
    except (OSError, ValueError):
        return False
    return all(_mtime_ns(Path(p)) == mtime for p, mtime in built.items())


def wait_for_compile(timeout: float = _LOCK_WAIT_TIMEOUT) -> None:
    """Block until the compile daemon has rewritten ``.web`` for the current inputs.

    Called by a backend worker that skips frontend compilation
    (``REFLEX_SKIP_COMPILE``) before it reads the stateful-pages marker. Waits
    while a compile is in progress, and otherwise while a built input changed
    since the last compile (the daemon has not picked the edit up yet).
    Returns when the build is current, when the daemon is gone, or after
    ``timeout``.

    Args:
        timeout: Maximum seconds to wait.
    """
    lock = _lock_path()
    deadline = time.monotonic() + timeout
    waited = False
    while time.monotonic() < deadline and daemon_active():
        if not path_ops.is_locked(lock) and _built_inputs_current():
            break
        if not waited:
            logger.debug(
                "Waiting for the compile daemon to finish the current compile."
            )
            waited = True
        time.sleep(0.02)


def _prepare_fork_parent(roots: list[Path]) -> None:
    """Make the warm parent a good fork base.

    Stops the framework's background threads (so ``_can_fork`` passes) and warms
    the per-process caches every child would otherwise rebuild: the first-party
    module classification and the compile cache's component-module lookups.

    Args:
        roots: The resolved reload roots.
    """
    from reflex.compiler import page_cache

    _quiesce_parent()
    _first_party_module_names(roots)
    page_cache.warm_module_file_cache()


def _child_compile(
    roots: list[Path],
    prerender_routes: bool,
    changed: set[Path] | None = None,
    predict: bool = False,
) -> None:
    """Reset first-party state, re-import the app fresh, and compile incrementally.

    Runs in a forked child (POSIX) or a one-shot subprocess (Windows). Must not
    return normally on error; the caller maps the exit code to success/failure.

    Args:
        roots: The resolved reload roots.
        prerender_routes: Whether to prerender routes during compile.
        changed: The paths the watcher reported for this reload, when known.
            Lets the incremental rebuild skip validating pages that depend on
            none of them.
        predict: Whether to predict dynamic state names (see
            ``disk_cache.set_dynamic_name_prediction``).
    """
    from reflex.compiler import disk_cache
    from reflex.utils import prerequisites

    disk_cache.set_changed_hint(changed)
    disk_cache.set_dynamic_name_prediction(predict)
    # Timed in three steps so every hot reload reports where it spent its time
    # (resetting state vs re-importing first-party code vs compiling).
    t0 = time.perf_counter()
    _reset_first_party(roots)
    t1 = time.perf_counter()
    app, _ = prerequisites.get_and_validate_app(reload=False)
    t2 = time.perf_counter()
    app._compile(prerender_routes=prerender_routes, use_rich=True, trigger="hot_reload")
    t3 = time.perf_counter()
    logger.info(
        f"Hot reload {t3 - t0:.2f}s (reset {t1 - t0:.2f}s, "
        f"reimport {t2 - t1:.2f}s, compile {t3 - t2:.2f}s)"
    )


def _await_child(pid: int) -> int:
    """Reap a forked compile child, killing it if it exceeds the watchdog timeout.

    Args:
        pid: The forked child's pid.

    Returns:
        The child's exit code; 1 on timeout or a signal (a signal-killed
        child, such as Ctrl-C during shutdown, is a quiet failure).
    """
    deadline = time.monotonic() + _COMPILE_TIMEOUT
    while True:
        done, status = os.waitpid(pid, os.WNOHANG)
        if done == pid:
            code = os.waitstatus_to_exitcode(status)
            return code if code >= 0 else 1
        if time.monotonic() > deadline:
            with contextlib.suppress(OSError):
                os.kill(pid, signal.SIGKILL)
            with contextlib.suppress(OSError):
                os.waitpid(pid, 0)
            logger.error("Compile child timed out; killed it, keeping last build.")
            return 1
        time.sleep(0.02)


def _quiesce_parent() -> None:
    """Stop the framework's own background threads before forking.

    The telemetry worker (a ``ThreadPoolExecutor`` thread) outlives the
    initial compile's ``compile`` event and would otherwise make every later
    ``_can_fork`` check fail, silently downgrading each hot reload to a cold
    subprocess. Anything the user's app started at import time is out of our
    hands and still forces the fallback.
    """
    from reflex.utils import telemetry

    telemetry.shutdown_executor()


def _os_thread_count() -> int | None:
    """Count this process's OS threads, including native ones Python cannot see.

    Returns:
        The thread count from ``/proc`` (Linux), else None.
    """
    try:
        with Path("/proc/self/status").open() as status:
            for line in status:
                if line.startswith("Threads:"):
                    return int(line.split()[1])
    except (OSError, ValueError):
        return None
    return None


def _can_fork() -> bool:
    """Whether forking is safe right now (POSIX and the process is single-threaded).

    Forking a multi-threaded process and then running Python (not exec) inherits
    locks held by threads that don't exist in the child. The
    user app, imported warm in the parent, may have started a background thread
    at import time, so this is checked per compile.

    Returns:
        True if a per-compile ``fork()`` is safe.
    """
    if not hasattr(os, "fork"):
        return False
    _quiesce_parent()
    if threading.active_count() == 1:
        # A native thread that just finished (the file watcher's, the progress
        # bar's) may still be winding down; give it a moment so the fork is
        # really single-threaded.
        deadline = time.monotonic() + 0.25
        while (count := _os_thread_count()) is not None and count > 1:
            if time.monotonic() > deadline:
                logger.warning(
                    f"Compile daemon: {count} OS threads still alive; "
                    "falling back to a cold subprocess."
                )
                return False
            time.sleep(0.005)
        return True
    others = [
        t.name for t in threading.enumerate() if t is not threading.current_thread()
    ]
    logger.warning(
        "Compile daemon: cannot fork a warm child while other threads are "
        f"alive ({', '.join(others)}); falling back to a cold subprocess."
    )
    return False


def _single_threaded() -> bool:
    """Whether this process runs one thread, so a ``fork()`` is safe.

    Returns:
        True if no other Python or OS thread is alive.
    """
    return threading.active_count() == 1 and (_os_thread_count() or 1) == 1


def compiled_in_predicting_child(attempt: Callable[[], bool]) -> bool:
    """Run a cold incremental compile in a forked child that predicts state names.

    A failed prediction has already registered states under other names, so
    it runs in a copy-on-write child. On any other outcome than a compile,
    the caller compiles exactly in this process (which also reports errors).

    Skipped where a caller already chose the mode, such as the daemon's
    exact retry.

    Args:
        attempt: Runs the incremental compile; returns True when it compiled.

    Returns:
        True when the child compiled.
    """
    from reflex.compiler import disk_cache

    if (
        disk_cache._predict_dynamic_names is not None
        or not hasattr(os, "fork")
        or not _single_threaded()
    ):
        return False
    pid = os.fork()
    if pid == 0:  # child
        code = 1
        try:
            disk_cache.set_dynamic_name_prediction(True)
            code = 0 if attempt() else 2
        except disk_cache.DynamicStatePredictionError as exc:
            _log_failed_prediction(exc)
        except BaseException:  # the caller's exact compile reports it
            pass
        finally:
            os._exit(code)
    return _await_child(pid) == 0


def _compile_once(
    roots: list[Path], prerender_routes: bool, changed: set[Path] | None = None
) -> bool:
    """Run one incremental compile in an isolated child; report success.

    The first child predicts dynamic state names, re-evaluating only the
    changed pages. When the prediction fails, a fresh child compiles again
    without it, re-evaluating every page that defines such states.

    Args:
        roots: The resolved reload roots.
        prerender_routes: Whether to prerender routes during compile.
        changed: The paths the watcher reported for this reload, when known.

    Returns:
        True if the child compiled successfully, else False.
    """
    code = _run_compile_child(roots, prerender_routes, changed, predict=True)
    if code == _RETRY_EXIT_CODE:
        code = _run_compile_child(roots, prerender_routes, changed, predict=False)
    return code == 0


def _log_failed_prediction(exc: Exception) -> None:
    """Report why a compile child gives up its dynamic state name prediction.

    Args:
        exc: The failed prediction.
    """
    logger.info(
        f"Compile cache: {exc}; compiling again, re-evaluating every page that "
        "defines dynamic states"
    )


def _run_compile_child(
    roots: list[Path],
    prerender_routes: bool,
    changed: set[Path] | None,
    *,
    predict: bool,
) -> int:
    """Compile in an isolated child process and return its exit code.

    Uses a copy-on-write ``fork()`` when safe (warm), else a fresh subprocess
    (Windows, or when the warm parent is no longer single-threaded).

    Args:
        roots: The resolved reload roots.
        prerender_routes: Whether to prerender routes during compile.
        changed: The paths the watcher reported for this reload, when known.
        predict: Whether the child predicts dynamic state names.

    Returns:
        0 on success, ``_RETRY_EXIT_CODE`` when the prediction failed, else
        a failure code.
    """
    from reflex.compiler import disk_cache

    if _can_fork():
        pid = os.fork()
        if pid == 0:  # child
            code = 0
            try:
                _child_compile(roots, prerender_routes, changed, predict)
            except disk_cache.DynamicStatePredictionError as exc:
                _log_failed_prediction(exc)
                code = _RETRY_EXIT_CODE
            except BaseException:  # report any failure, never crash the daemon
                logger.exception("Hot reload compile failed.")
                code = 1
            finally:
                os._exit(code)
        return _await_child(pid)

    # No fork (Windows) or unsafe to fork: a fresh (cold) subprocess compiles.
    env = {**os.environ}
    if changed is not None:
        env[_CHANGED_ENV] = "\n".join(sorted(str(p) for p in changed))
    if predict:
        env[_PREDICT_ENV] = "1"
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "reflex.utils.compile_daemon", "--once"],
            check=False,
            timeout=_COMPILE_TIMEOUT,
            env=env,
        )
    except subprocess.TimeoutExpired:
        logger.error("Compile subprocess timed out; keeping the last good build.")
        return 1
    return proc.returncode


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
        with _compile_lock(root), log.timing(logger, "Compile daemon: initial compile"):
            if os.environ.pop("REFLEX_COMPILE_DAEMON_PRECOMPILED", None):
                prerequisites.get_app()
            else:
                prerequisites.get_compiled_app(
                    reload=False,
                    prerender_routes=prerender_routes,
                    use_rich=True,
                    trigger="initial",
                )
    except BaseException:  # tolerate a broken initial state; keep watching
        logger.exception("Initial compile failed; watching for a fix.")
    _prepare_fork_parent(roots)

    state = _WatchState.build(roots, root)
    state.checkpoint = _dependency_snapshot(state)
    logger.info("Compile daemon ready (warm); watching for changes.")
    # The first snapshot is the watch baseline; edits made since the last build
    # wrote the manifest raise no event, so compile them now.
    if not (pending := _unbuilt_changes(state)):
        _record_built_inputs(_known_snapshot(state, state.checkpoint))

    def alive() -> bool:
        # Never outlive reflex-run: if our parent died we were reparented.
        return os.getppid() == parent_pid

    # Changes a failed compile never applied. The manifest only moves on a
    # successful compile, so they stay in the changed hint until one succeeds;
    # otherwise the hint's stat-free hit shortcut would reuse their pages.
    unapplied: set[Path] = set()
    while alive():
        changed = pending or _next_changes(state, alive)
        pending = set()
        if not changed:
            break
        changed = changed | unapplied
        from reflex.compiler.disk_cache import format_path_list

        logger.info(
            f"Compile daemon: change detected in {format_path_list(map(str, changed), root)}"
        )

        # A change to a genuinely-global input (rxconfig/lockfiles, or a reflex
        # upgrade) can't be applied to the warm parent (it imported the old
        # version); re-exec the daemon so the new world is actually loaded.
        if changed & state.globals_:
            logger.info("Global config changed; restarting compile daemon.")
            os.execv(
                sys.executable, [sys.executable, "-m", "reflex.utils.compile_daemon"]
            )

        before = (
            state.checkpoint
            if state.checkpoint is not None
            else _dependency_snapshot(state)
        )
        state.roots = roots = _reload_roots()
        with _compile_lock(root):
            ok = _compile_once(roots, prerender_routes, changed)
            # Refresh what is watched from the new manifest so a newly
            # referenced content file becomes watched.
            state = _WatchState.build(roots, root)
            state.checkpoint = _dependency_snapshot(state)
            # Also after a failure: workers must not wait on an edit that will
            # not build; a fix is a newer edit. An input edited during the
            # compile keeps its earlier time, so workers wait for its compile.
            _record_built_inputs(_known_snapshot(state, {**state.checkpoint, **before}))
        unapplied = set() if ok else changed
        if not ok:
            logger.error("Compile failed; keeping the last good build.")
        # Catch up on edits made while the watcher was down for the compile. An
        # input the compile started to read was not watched before it; it
        # changed unless the compile recorded its current content.
        pending = _missed_changes(before, state.checkpoint)
        if appeared := (pending - before.keys()) & state.known:
            pending -= _built_inputs(appeared)


def main(argv: list[str] | None = None) -> int:
    """Entry point for ``python -m reflex.utils.compile_daemon``.

    Args:
        argv: Command-line arguments (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code.
    """
    argv = sys.argv[1:] if argv is None else argv
    if "--once" in argv:
        changed_env = os.environ.get(_CHANGED_ENV)
        changed = (
            {Path(line) for line in changed_env.splitlines() if line}
            if changed_env is not None
            else None
        )
        from reflex.compiler import disk_cache

        try:
            _child_compile(
                _reload_roots(),
                bool(os.environ.get("REFLEX_PRERENDER_ROUTES")),
                changed,
                bool(os.environ.get(_PREDICT_ENV)),
            )
        except disk_cache.DynamicStatePredictionError as exc:
            _log_failed_prediction(exc)
            return _RETRY_EXIT_CODE
        except BaseException:  # report any failure, never crash
            logger.exception("Hot reload compile failed.")
            return 1
        return 0
    # Held for the process lifetime, so backend workers defer to this daemon
    # exactly while it lives (see ``daemon_active``). Forked compile children
    # share the lock; ``os.execv`` drops it and the new image retakes it.
    try:
        descriptor = _acquire_lock(_daemon_lock_path())
    except OSError as exc:
        logger.warning(
            f"Compile daemon: this file system cannot lock files ({exc}); "
            "backend workers compile instead."
        )
        return 0
    if descriptor is None:
        logger.warning(
            "Another compile daemon owns this project's .web; leaving the "
            "compiles to it."
        )
        return 0
    try:
        _serve()
    except KeyboardInterrupt:
        return 0  # clean shutdown (Ctrl-C); no traceback
    return 0


if __name__ == "__main__":
    # ``python -m`` executes this file as ``__main__``, a second copy of the
    # module. Run the importable module instead, so its logger sits in the
    # ``reflex`` tree and no state is split between two copies.
    from reflex.utils.compile_daemon import main as _main

    sys.exit(_main())
