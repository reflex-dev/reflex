"""Per-page dependency discovery for the incremental compile cache.

Each page records the first-party Python import closure of its page callable,
files read during page evaluation, component modules in its rendered tree, and
fine-grained state files it references. ``disk_cache`` persists hashes of that
set so only pages whose dependencies changed need to be recompiled.
"""

from __future__ import annotations

import builtins
import contextlib
import hashlib
import importlib
import importlib.util
import os
import re
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from contextvars import ContextVar
from importlib import metadata
from pathlib import Path
from typing import TYPE_CHECKING

from reflex_base.environment import environment

if TYPE_CHECKING:
    from reflex_base.components.component import BaseComponent
    from reflex_base.plugins import PageContext

#: A manifest file-table entry: ``[content sha256, st_mtime_ns, st_size]``.
FileEntry = list

#: Directories never worth hashing (build artifacts, deps, caches).
_SKIP_DIRS = {".web", ".venv", "venv", "node_modules", "__pycache__", ".git", "assets"}

#: Genuinely-global files: a change here can affect every page's output, so it
#: bumps ``global_epoch`` rather than any single page's dependency set.
#: ``reflex.lock/`` is deliberately absent: its lockfiles are derived from
#: inputs tracked elsewhere (``rxconfig.py`` frontend packages, page imports,
#: the Reflex version) and are rewritten by every install, so treating them as
#: inputs made every reload fall back to a full compile.
_GLOBAL_FILES = (
    "rxconfig.py",
    "uv.lock",
    "pyproject.toml",
    "requirements.txt",
    "package.json",
)

#: Matches a JS state-context identifier in compiled page output.
STATE_CONTEXT_RE = re.compile(r"reflex___state[A-Za-z0-9_]+")


def _sha(*parts: bytes | str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode() if isinstance(p, str) else p)
        h.update(b"\x1f")
    return h.hexdigest()


def _reflex_version() -> str:
    try:
        return metadata.version("reflex")
    except Exception:
        return "unknown"


def first_party_roots(root: Path | None = None) -> tuple[Path, ...]:
    """The directories whose Python files count as the app's own source.

    The project root plus ``REFLEX_HOT_RELOAD_INCLUDE_PATHS`` (a sibling local
    package the backend reloader also watches). Files under any of these are
    hashed into page dependency sets; everything else is an installed
    dependency whose change flows through the version/epoch instead.

    Args:
        root: Project root. Defaults to cwd.

    Returns:
        The resolved roots, project root first.
    """
    root = (root or Path.cwd()).resolve()
    include = tuple(
        Path(p).resolve() for p in environment.REFLEX_HOT_RELOAD_INCLUDE_PATHS.get()
    )
    return (root, *(p for p in include if p != root))


def _under_any(path: Path, roots: Iterable[Path]) -> bool:
    """Whether ``path`` is nested below (or is) one of ``roots``.

    Args:
        path: Absolute path to test.
        roots: Absolute root paths.

    Returns:
        True when some root contains ``path``.
    """
    return any(root == path or root in path.parents for root in roots)


# A page's markdown/data dependencies are read lazily while the page is
# evaluated. Track those reads only while ``record_reads`` is active, so the
# idle overhead is one contextvar read.

_active_reads: ContextVar[set[str] | None] = ContextVar("_active_reads", default=None)
_patched = False
_recorder_root: Path | None = None

#: Path parts that mark a dependency/build location whose reads are never a
#: page's own source dependency (a change there flows through the version/epoch).
_EXCLUDE_PARTS = _SKIP_DIRS | {"site-packages", "dist-packages"}

#: Suffixes of content files a page may read from *outside* the project root
#: (e.g. the docs app reads its markdown from a sibling directory). Reads under
#: the project root are tracked regardless of suffix; reads elsewhere only if
#: they look like content, so stdlib/site reads of other types are ignored.
_CONTENT_SUFFIXES = {
    ".md",
    ".mdx",
    ".py",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".txt",
    ".csv",
    ".html",
    ".rst",
}

_PYTHON_PREFIXES = tuple(
    Path(prefix).resolve()
    for prefix in {sys.base_exec_prefix, sys.base_prefix, sys.exec_prefix, sys.prefix}
    if prefix
)
#: Maps a module's raw ``__file__`` value to its recordable resolved path (or
#: None). Cleared by ``enable_read_tracking`` when the recorder root changes.
_module_file_cache: dict[object, str | None] = {}
_app_import_reads: dict[Path, set[str]] = {}


@contextlib.contextmanager
def _suspend_tracking():
    """Ignore read/import hooks caused by dependency bookkeeping.

    Yields:
        None.
    """
    token = _active_reads.set(None)
    try:
        yield
    finally:
        _active_reads.reset(token)


def _record_read(path: object) -> None:
    target = _active_reads.get()
    if target is None:
        return
    with _suspend_tracking():
        try:
            resolved = Path(path).resolve()  # type: ignore[arg-type]
        except (OSError, TypeError, ValueError):
            return
        if any(part in _EXCLUDE_PARTS for part in resolved.parts):
            return
        root = _recorder_root
        under_root = root is not None and _under_any(resolved, first_party_roots(root))
        if not under_root and resolved.suffix.lower() not in _CONTENT_SUFFIXES:
            return
        target.add(str(resolved))


def _is_inside(path: Path, root: Path) -> bool:
    """Return whether ``path`` is nested below ``root``.

    Args:
        path: Absolute path to test.
        root: Absolute root path.

    Returns:
        True when ``path`` is nested below ``root``.
    """
    return root in path.parents


def _is_python_install_file(path: Path) -> bool:
    """Return whether ``path`` is under this interpreter's install roots.

    Args:
        path: Absolute path to test.

    Returns:
        True when ``path`` is under the interpreter or virtualenv prefix.
    """
    return any(prefix in path.parents for prefix in _PYTHON_PREFIXES)


def _recordable_module_file(file: object) -> str | None:
    """Resolve a module file only when it can be a first-party dependency.

    Args:
        file: The imported module's ``__file__`` value.

    Returns:
        The resolved module file path to record, or None when it is outside the
        project root or otherwise not recordable.
    """
    root = _recorder_root
    if root is None:
        return None
    # Hot path: every import statement under an active recorder lands here, so
    # look up the raw ``__file__`` value before any Path construction. Keying
    # by the raw value is safe because ``enable_read_tracking`` clears the
    # cache whenever the recorder root changes.
    try:
        return _module_file_cache[file]
    except KeyError:
        pass
    except TypeError:
        return None

    with _suspend_tracking():
        try:
            path = Path(file).absolute()  # type: ignore[arg-type]
        except (OSError, TypeError, ValueError):
            return None

        roots = first_party_roots(root)
        resolved_str = None
        if not any(part in _EXCLUDE_PARTS for part in path.parts) and (
            _under_any(path, roots) or not _is_python_install_file(path)
        ):
            try:
                resolved = path.resolve()
            except (OSError, TypeError, ValueError):
                pass
            else:
                if not any(part in _EXCLUDE_PARTS for part in resolved.parts):
                    resolved_str = (
                        str(resolved) if _under_any(resolved, roots) else None
                    )
        _module_file_cache[file] = resolved_str
        return resolved_str


def _record_module_file(module: object, target: set[str]) -> None:
    """Record the source file for an imported module, if it has one.

    Args:
        module: The imported module object.
        target: The active read set.
    """
    file = getattr(module, "__file__", None)
    if not file:
        return
    if resolved_file := _recordable_module_file(file):
        target.add(resolved_file)


def _absolute_import_name(
    name: str, globals_: dict[str, object] | None, level: int
) -> str:
    """Resolve an import name relative to the caller package.

    Args:
        name: The import name passed to ``__import__``.
        globals_: The caller globals passed to ``__import__``.
        level: The relative import level.

    Returns:
        The absolute module name when it can be resolved, else ``name``.
    """
    if not level:
        return name
    package = None
    if globals_ is not None:
        package = globals_.get("__package__")
        if not package and (module := globals_.get("__name__")):
            package = (
                module
                if isinstance(module, str) and globals_.get("__path__") is not None
                else module.rpartition(".")[0]
                if isinstance(module, str)
                else None
            )
    if not isinstance(package, str):
        return name
    with contextlib.suppress(Exception):
        return importlib.util.resolve_name(f"{'.' * level}{name}", package)
    return name


def _record_imported_modules(
    name: str,
    result: object,
    target: set[str],
    fromlist: Sequence[str] | None = None,
) -> None:
    """Record source files for modules imported while a recorder is active.

    Args:
        name: The absolute requested module name.
        result: The object returned by ``__import__`` or ``import_module``.
        target: The active read set.
        fromlist: The ``fromlist`` passed to ``__import__``.
    """
    _record_module_file(result, target)
    result_id = id(result)
    if (module := sys.modules.get(name)) and id(module) != result_id:
        _record_module_file(module, target)
    if not fromlist:
        return
    for item in fromlist:
        if (
            item != "*"
            and (module := sys.modules.get(f"{name}.{item}"))
            and id(module) != result_id
        ):
            _record_module_file(module, target)


def enable_read_tracking(root: Path | None = None) -> None:
    """Install per-page source-read tracking and register the recorder hook.

    Idempotent. Patches ``Path.read_text``/``read_bytes`` and ``open`` to record
    reads (only while a recording set is active) and points the reflex-base
    compile loop at :func:`record_reads`. Called when an incremental cache flag
    is on; a no-op to the compile otherwise.

    Args:
        root: Project root; only reads under it are recorded. Defaults to cwd.
    """
    global _patched, _recorder_root
    resolved_root = (root or Path.cwd()).resolve()
    if _recorder_root != resolved_root:
        _module_file_cache.clear()
    _recorder_root = resolved_root

    from reflex_base.plugins import compiler as _bc

    _bc.page_source_recorder = record_reads

    if _patched:
        return
    _patched = True

    orig_read_text = Path.read_text
    orig_read_bytes = Path.read_bytes
    orig_path_open = Path.open
    orig_open = builtins.open
    orig_import = builtins.__import__
    orig_import_module = importlib.import_module

    def _is_read_mode(mode: str) -> bool:
        return "r" in mode and not ("w" in mode or "a" in mode or "x" in mode)

    def read_text(self: Path, *args: object, **kwargs: object):
        _record_read(self)
        return orig_read_text(self, *args, **kwargs)  # type: ignore[arg-type]

    def read_bytes(self: Path):
        _record_read(self)
        return orig_read_bytes(self)

    # ``Path.open`` calls ``io.open`` directly (not ``builtins.open``), so it
    # needs its own patch for reads through it to be recorded.
    def path_open(self: Path, mode: str = "r", *args: object, **kwargs: object):
        if _is_read_mode(mode):
            _record_read(self)
        return orig_path_open(self, mode, *args, **kwargs)  # type: ignore[arg-type]

    def open_(file: object, mode: str = "r", *args: object, **kwargs: object):
        if _is_read_mode(mode):
            _record_read(file)
        return orig_open(file, mode, *args, **kwargs)  # type: ignore[arg-type]

    def import_(
        name: str,
        globals_: dict[str, object] | None = None,
        locals_: dict[str, object] | None = None,
        fromlist: Sequence[str] | None = (),
        level: int = 0,
    ):
        result = orig_import(name, globals_, locals_, fromlist, level)
        if (target := _active_reads.get()) is not None:
            _record_imported_modules(
                _absolute_import_name(name, globals_, level),
                result,
                target,
                fromlist,
            )
        return result

    def import_module(name: str, package: str | None = None):
        result = orig_import_module(name, package)
        if (target := _active_reads.get()) is not None:
            _record_imported_modules(result.__name__, result, target)
        return result

    Path.read_text = read_text  # type: ignore[method-assign,assignment]
    Path.read_bytes = read_bytes  # type: ignore[method-assign,assignment]
    Path.open = path_open  # type: ignore[method-assign,assignment]
    builtins.open = open_  # type: ignore[assignment]
    builtins.__import__ = import_  # type: ignore[assignment]
    importlib.import_module = import_module


@contextlib.contextmanager
def record_reads():
    """Record source-file reads on the current task into a fresh set.

    Yields:
        The set of resolved source-file path strings read within the block.
    """
    reads: set[str] = set()
    token = _active_reads.set(reads)
    try:
        yield reads
    finally:
        _active_reads.reset(token)


@contextlib.contextmanager
def record_app_import(root: Path | None = None):
    """Record files read/imported while importing the app module.

    Args:
        root: Project root. Defaults to cwd.

    Yields:
        None.
    """
    root = (root or Path.cwd()).resolve()
    recorded: set[str] = set()
    success = False
    try:
        with record_reads() as reads:
            yield
            recorded = set(reads)
            success = True
    finally:
        if success:
            _app_import_reads[root] = recorded


def _app_entrypoint_file(root: Path | None = None) -> Path | None:
    """Resolve the user's app entrypoint module file (where ``rx.App`` is built).

    App-wide inputs like theme, app wraps, the toaster, stylesheets, and head
    components are configured here, not in any single page's
    dependency set. This is the root of :func:`app_dependency_files`, which walks
    its imports (stopping at page modules) to find the config-only modules whose
    change must invalidate the reused on-disk app-wide files.

    Args:
        root: Project root; only a file under it is returned. Defaults to cwd.

    Returns:
        The resolved entrypoint file path under ``root``, or None if it can't be
        determined (no app module imported, or it lives outside ``root``).
    """
    try:
        from reflex.config import get_config

        module = get_config().module
    except Exception:
        return None
    file = getattr(sys.modules.get(module), "__file__", None)
    if not file:
        return None
    rf = Path(file).resolve()
    root = (root or Path.cwd()).resolve()
    return rf if root in rf.parents else None


def global_epoch_inputs(
    root: Path | None = None, *, pages: Sequence[object] | None = None
) -> dict[str, str]:
    """Fingerprint each genuinely-global input individually.

    These can affect every page's output but belong to no single page, so they
    gate the whole cache rather than any one page's dependency set: the Reflex
    version, the config/lockfiles, and the app-level config files: the app
    entrypoint module plus the config-only modules it imports (theme, app-wraps,
    stylesheets, head components; see :func:`app_dependency_files`). Kept small
    on purpose; per-file edits flow through per-page dependency sets instead.

    Keeping each input's digest separate (rather than one combined sha) lets a
    mismatch report *which* global input changed.

    Args:
        root: Project root. Defaults to cwd.
        pages: The current page definitions, used as barriers so page modules
            (tracked per page) are excluded from the app-level config files.

    Returns:
        A mapping of input label (``reflex``, a global filename, or
        ``app:<path>``) to its content digest (``<absent>`` if unreadable).
    """
    root = (root or Path.cwd()).resolve()
    inputs: dict[str, str] = {"reflex": _reflex_version()}
    for name in _GLOBAL_FILES:
        path = root / name
        try:
            inputs[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            inputs[name] = "<absent>"
    for path_str in app_dependency_files(pages, root):
        try:
            digest = hashlib.sha256(Path(path_str).read_bytes()).hexdigest()
        except OSError:
            digest = "<absent>"
        inputs[f"app:{path_str}"] = digest
    return inputs


def global_input_paths(
    root: Path | None = None, *, pages: Sequence[object] | None = None
) -> dict[str, str]:
    """Map each file-backed global input label to its path.

    The manifest stores these labels with their paths and keeps the content
    entries in its file table, so validation is stat-first like page deps.

    Args:
        root: Project root. Defaults to cwd.
        pages: The current page definitions (see :func:`global_epoch_inputs`).

    Returns:
        ``{label: path}`` for every global input except the Reflex version.
    """
    root = (root or Path.cwd()).resolve()
    paths = {name: str(root / name) for name in _GLOBAL_FILES}
    paths.update({f"app:{p}": p for p in app_dependency_files(pages, root)})
    return paths


def global_epoch(
    root: Path | None = None, *, pages: Sequence[object] | None = None
) -> str:
    """Fingerprint the genuinely-global inputs as one digest.

    Args:
        root: Project root. Defaults to cwd.
        pages: The current page definitions (see :func:`global_epoch_inputs`).

    Returns:
        A hex digest of the global inputs.
    """
    # Sorted for a deterministic digest regardless of dict insertion order.
    return _sha(
        *(f"{k}={v}" for k, v in sorted(global_epoch_inputs(root, pages=pages).items()))
    )


def _module_file(component: object) -> Path | None:
    mod = sys.modules.get(getattr(component, "__module__", "") or "")
    file = getattr(mod, "__file__", None)
    return Path(file) if file else None


#: Component/state class -> its resolved first-party module file (or None).
#: A rendered tree has tens of thousands of nodes but few distinct classes,
#: and a class's module never moves; resolving per node dominated the
#: dependency walk. Warmed in the daemon parent so forked children inherit it.
_class_file_cache: dict[type, Path | None] = {}


def _class_module_file(cls: type, roots: tuple[Path, ...]) -> Path | None:
    """Resolve a class's module file when it is first-party.

    Args:
        cls: The component or state class.
        roots: The first-party roots.

    Returns:
        The resolved module file under one of ``roots``, else None.
    """
    try:
        return _class_file_cache[cls]
    except KeyError:
        pass
    f = _module_file(cls)
    resolved = None
    if f is not None:
        rf = f.resolve()
        if _under_any(rf, roots):
            resolved = rf
    _class_file_cache[cls] = resolved
    return resolved


def warm_module_file_cache(root: Path | None = None) -> None:
    """Pre-resolve the module file of every loaded component and state class.

    Args:
        root: Project root. Defaults to cwd.
    """
    from reflex_base.components.component import Component

    from reflex.state import BaseState

    roots = first_party_roots(root)
    for base in (Component, BaseState):
        for cls in _subclasses(base):
            _class_module_file(cls, roots)


def component_module_files(
    root_component: object, root: Path | None = None
) -> set[Path]:
    """Resolve the first-party module files of every component in a tree.

    Walks the rendered component tree and collects each component class module
    under ``root``. This catches component dependencies that static imports may
    miss.

    Args:
        root_component: The page's root component (its rendered tree).
        root: Project root; only files under it are returned. Defaults to cwd.

    Returns:
        The set of resolved first-party module files the tree depends on.
    """
    roots = first_party_roots(root)
    files: set[Path] = set()
    seen: set[int] = set()
    stack: list[object] = [root_component]
    while stack:
        comp = stack.pop()
        if id(comp) in seen:
            continue
        seen.add(id(comp))
        if (rf := _class_module_file(type(comp), roots)) is not None:
            files.add(rf)
        children = getattr(comp, "children", None)
        if children:
            stack.extend(children)
    return files


#: Cache of the first-party import graph, keyed by project root.
_import_graph_cache: dict[Path, dict[str, set[str]]] = {}


def _resolve_module_file(name: str) -> str | None:
    mod = sys.modules.get(name)
    file = getattr(mod, "__file__", None)
    return str(Path(file).resolve()) if file else None


def _loaded_first_party_modules(root: Path) -> dict[str, str]:
    """Map first-party module files to module names.

    Args:
        root: Resolved project root.

    Returns:
        A mapping of resolved file path -> module name for loaded modules under
        ``root``.
    """
    roots = first_party_roots(root)
    file_to_mod: dict[str, str] = {}
    for name, mod in list(sys.modules.items()):
        file = getattr(mod, "__file__", None)
        if not file:
            continue
        rf = Path(file).resolve()
        if _under_any(rf, roots):
            file_to_mod[str(rf)] = name
    return file_to_mod


def _import_from_targets(node: object, modname: str) -> list[str]:
    """Resolve a ``from ... import ...`` node to candidate module names.

    Handles relative imports via the importing module's package. Returns the
    base module and each ``base.name``. A name may be a submodule or an
    attribute; both candidates are resolved against ``sys.modules`` by the
    caller.

    Args:
        node: An ``ast.ImportFrom`` node.
        modname: The dotted name of the module containing the import.

    Returns:
        Candidate dotted module names to resolve.
    """
    import ast

    if not isinstance(node, ast.ImportFrom):
        return []
    if node.level:  # relative import: walk up from the importing package
        base_pkg = modname.rsplit(".", node.level)[0] if "." in modname else ""
        base = f"{base_pkg}.{node.module}" if node.module else base_pkg
    else:
        base = node.module or ""
    if not base:
        return []
    return [base, *(f"{base}.{a.name}" for a in node.names)]


#: file -> ((st_mtime_ns, st_size), imported dotted names). Parsing every
#: first-party module on every hot reload is the cost this avoids; the daemon
#: persists it in the manifest so a fresh process only parses changed files.
_import_names_cache: dict[str, tuple[tuple[int, int], list[str]]] = {}


def _stat_key(path: str) -> tuple[int, int] | None:
    """Return ``(st_mtime_ns, st_size)`` for ``path``, or None if unreadable.

    Args:
        path: The file path.

    Returns:
        The stat key, or None.
    """
    try:
        st = Path(path).stat()
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size)


def load_import_names_cache(data: Mapping[str, Sequence[object]]) -> None:
    """Seed the import-name parse cache from its persisted form.

    Args:
        data: ``{path: [[mtime_ns, size], [names...]]}`` as written by
            :func:`export_import_names_cache`.
    """
    _import_names_cache.clear()
    for path, entry in data.items():
        if (
            isinstance(entry, Sequence)
            and len(entry) == 2
            and isinstance(entry[0], Sequence)
            and len(entry[0]) == 2
            and all(isinstance(n, int) for n in entry[0])
            and isinstance(entry[1], Sequence)
        ):
            key = (int(entry[0][0]), int(entry[0][1]))  # type: ignore[index]
            _import_names_cache[path] = (key, [str(n) for n in entry[1]])


def export_import_names_cache() -> dict[str, list[object]]:
    """Return the import-name parse cache in its persisted form.

    Returns:
        ``{path: [[mtime_ns, size], [names...]]}``.
    """
    return {
        path: [list(key), names] for path, (key, names) in _import_names_cache.items()
    }


def _module_import_names(file: str, modname: str) -> list[str]:
    """Return the dotted names one module imports (statically).

    Cached by the file's stat key, so an unchanged file is never re-parsed.

    Args:
        file: The resolved module file path.
        modname: The module's dotted name.

    Returns:
        The imported dotted-name candidates (see :func:`_import_from_targets`).
    """
    import ast

    key = _stat_key(file)
    cached = _import_names_cache.get(file)
    if cached is not None and key is not None and cached[0] == key:
        return cached[1]
    names: list[str] = []
    try:
        tree = ast.parse(Path(file).read_bytes())
    except (OSError, SyntaxError, ValueError):
        return names
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.extend(_import_from_targets(node, modname))
    if key is not None:
        _import_names_cache[file] = (key, names)
    return names


def _module_import_edges(
    file: str, modname: str, file_to_mod: dict[str, str]
) -> set[str]:
    """Return first-party files imported by one module.

    Args:
        file: The resolved module file path.
        modname: The module's dotted name.
        file_to_mod: Loaded first-party module files.

    Returns:
        The resolved first-party files imported by ``file``.
    """
    deps: set[str] = set()
    for name in _module_import_names(file, modname):
        target = _resolve_module_file(name)
        if target is not None and target in file_to_mod:
            deps.add(target)
    return deps


def build_import_graph(root: Path | None = None) -> dict[str, set[str]]:
    """Build the first-party import graph (file -> files it imports).

    Parses already-imported first-party modules and resolves their imports to
    files under ``root`` via ``sys.modules``. Cached per root for the duration of
    the process.

    Args:
        root: Project root. Defaults to cwd.

    Returns:
        A mapping of resolved file path -> the set of first-party files it imports.
    """
    root = (root or Path.cwd()).resolve()
    cached = _import_graph_cache.get(root)
    if cached is not None:
        return cached

    file_to_mod = _loaded_first_party_modules(root)
    graph = {
        file: _module_import_edges(file, modname, file_to_mod)
        for file, modname in file_to_mod.items()
    }
    _import_graph_cache[root] = graph
    return graph


def clear_import_graph() -> None:
    """Drop cached import graphs (e.g. after modules are reloaded)."""
    _import_graph_cache.clear()
    _app_import_reads.clear()


def _walk_import_closure(
    graph: dict[str, set[str]],
    starts: set[str],
    barriers: set[str] | None = None,
) -> set[str]:
    """Walk a first-party import graph from ``starts``.

    Args:
        graph: Mapping of source file to imported source files.
        starts: Source files where traversal begins.
        barriers: Files included elsewhere and not traversed into.

    Returns:
        The reachable source files, excluding barriers.
    """
    barriers = barriers or set()
    seen: set[str] = set()
    stack = list(starts - barriers)
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(dep for dep in graph.get(cur, ()) if dep not in barriers)
    return seen


def _component_source_files(component: object, root: Path) -> set[str]:
    """The component callable's own defining files under ``root``.

    The callable's *real* code filename (``__code__``, correct even when
    ``__module__`` was reassigned, as the docs app does for generated pages) plus
    its module file. These are the roots a page's import closure walks from, and
    the barriers the app-config walk stops at.

    Args:
        component: The page component or callable.
        root: Resolved project root; only files under it are returned.

    Returns:
        The set of resolved defining file path strings under ``root``.
    """
    out: set[str] = set()
    roots = first_party_roots(root)
    code = getattr(component, "__code__", None)
    filename = getattr(code, "co_filename", None)
    own = _module_file(component)
    for path in (filename, own):
        if path:
            rf = Path(path).resolve()
            if _under_any(rf, roots):
                out.add(str(rf))
    return out


def page_py_dependencies(
    component: BaseComponent | object, root: Path | None = None
) -> set[str]:
    """Return the transitive first-party ``.py`` files a page's code depends on.

    Starts from the page callable's code filename plus its module file, then
    walks the import graph. This captures function-based views and shared
    helpers that the rendered-tree walk cannot see.

    Args:
        component: The page component or callable.
        root: Project root. Defaults to cwd.

    Returns:
        The set of resolved first-party ``.py`` dependency file paths.
    """
    root = (root or Path.cwd()).resolve()
    graph = build_import_graph(root)
    return _walk_import_closure(graph, _component_source_files(component, root))


def module_py_dependencies(module_file: str, root: Path | None = None) -> set[str]:
    """Return the transitive first-party ``.py`` files a module depends on.

    Args:
        module_file: The module's resolved source file path.
        root: Project root. Defaults to cwd.

    Returns:
        The reachable first-party dependency file paths, including
        ``module_file`` itself.
    """
    root = (root or Path.cwd()).resolve()
    return _walk_import_closure(build_import_graph(root), {module_file})


def app_dependency_files(
    pages: Sequence[object] | None = None, root: Path | None = None
) -> set[str]:
    """First-party files whose change affects app-level config (not any page).

    Walks the first-party import graph from the app entrypoint
    (:func:`_app_entrypoint_file`), treating each page-defining module as a
    barrier (not entered), then folds in files read/imported while the app module
    loaded. Static page dependency closures are removed from that dynamic set so
    regular page edits still invalidate per-page rather than globally. A config
    module shared with a page is still captured when it is reached from the
    entrypoint directly.

    These configure the app-wide files an incremental rebuild reuses on disk
    (app root, contexts, theme, stylesheet), so they are folded into
    :func:`global_epoch`: editing one forces a full recompile instead of leaving
    those files stale.

    Args:
        pages: The current page definitions, used as traversal barriers. When
            None (no page set available), no barriers apply.
        root: Project root. Defaults to cwd.

    Returns:
        The set of resolved app-config dependency file path strings, or empty if
        the entrypoint can't be resolved.
    """
    root = (root or Path.cwd()).resolve()
    entrypoint = _app_entrypoint_file(root)
    if entrypoint is None:
        return set()
    graph = build_import_graph(root)
    barriers: set[str] = set()
    page_deps: set[str] = set()
    for page in pages or ():
        starts = _component_source_files(getattr(page, "component", None), root)
        barriers |= starts
        page_deps |= _walk_import_closure(graph, starts)

    start = str(entrypoint)
    static_deps = _walk_import_closure(graph, {start}, barriers)
    dynamic_deps = _app_import_reads.get(root, set()) - page_deps
    return static_deps | dynamic_deps


def file_entry(path: str) -> FileEntry | None:
    """Read a file once and describe it for the manifest file table.

    Args:
        path: The file path.

    Returns:
        ``[sha256, st_mtime_ns, st_size]``, or None if unreadable.
    """
    try:
        with Path(path).open("rb") as fh:
            st = os.fstat(fh.fileno())
            digest = hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return None
    return [digest, st.st_mtime_ns, st.st_size]


def make_hasher() -> Callable[[str], FileEntry | None]:
    """Return a file-table entry builder that memoizes each path within one compile.

    Shared component files appear in many pages' dependency sets; reading each
    file at most once keeps manifest writes cheap.

    Returns:
        A function mapping a path string to its :func:`file_entry` (None if
        unreadable).
    """
    cache: dict[str, FileEntry | None] = {}

    def hasher(path: str) -> FileEntry | None:
        if path not in cache:
            cache[path] = file_entry(path)
        return cache[path]

    return hasher


class FileValidator:
    """Decide whether recorded files still match their manifest entries.

    Validation is stat-first: a file whose ``(mtime_ns, size)`` still matches
    its entry is unchanged without being read. Only a file whose stat moved is
    hashed, and a touch that left the content identical counts as unchanged
    (its refreshed entry is exposed in ``refreshed`` so the manifest can stop
    re-hashing it). Each path is examined at most once per compile.
    """

    def __init__(self, files: Mapping[str, Sequence[object]]) -> None:
        """Bind the validator to a manifest file table.

        Args:
            files: ``{path: [sha256, mtime_ns, size]}``.
        """
        self._files = files
        self._changed: dict[str, bool] = {}
        self.refreshed: dict[str, FileEntry] = {}

    def changed(self, path: str) -> bool:
        """Whether ``path`` differs from its recorded entry (or has none).

        Args:
            path: The file path.

        Returns:
            True if the file changed, is unreadable, or is not in the table.
        """
        cached = self._changed.get(path)
        if cached is not None:
            return cached
        entry = self._files.get(path)
        result = True
        if entry is not None and len(entry) == 3:
            key = _stat_key(path)
            if key is not None and (key[0], key[1]) == (entry[1], entry[2]):
                result = False
            elif (fresh := file_entry(path)) is not None and fresh[0] == entry[0]:
                self.refreshed[path] = fresh
                result = False
        self._changed[path] = result
        return result

    def unchanged(self, paths: Iterable[str]) -> bool:
        """Whether every file in ``paths`` is unchanged.

        Args:
            paths: The recorded dependency paths of one page.

        Returns:
            True if no file changed.
        """
        return not any(self.changed(path) for path in paths)


def _subclasses(root_cls: type) -> list[type]:
    seen: set[type] = set()
    out: list[type] = []
    stack = [root_cls]
    while stack:
        cls = stack.pop()
        if cls in seen:
            continue
        seen.add(cls)
        out.append(cls)
        stack.extend(cls.__subclasses__())
    return out


def state_dependency_index(
    root: Path | None = None,
) -> tuple[dict[str, Path], set[Path]]:
    """Build the state-context -> file index for fine-grained invalidation.

    A page references the JS state-context identifier
    ``format_state_name(state.get_full_name())`` in its output; mapping that to
    the state's module file lets a state edit invalidate only its dependents.
    Only *pure* state modules under ``root`` (no Component defined in them) are
    fine-grained; mixed state/component modules stay coarse (in the shared
    fingerprint) so a component edit there is never missed.

    Args:
        root: Project root. Defaults to cwd.

    Returns:
        ``(identifier_to_file, fine_state_files)``.
    """
    roots = first_party_roots(root)
    from reflex_base.components.component import Component
    from reflex_base.utils import format as fmt

    from reflex.state import BaseState

    component_files = {
        rf for cls in _subclasses(Component) if (rf := _class_module_file(cls, roots))
    }
    id_to_file: dict[str, Path] = {}
    state_files: set[Path] = set()
    for cls in _subclasses(BaseState):
        rf = _class_module_file(cls, roots)
        if rf is None:
            continue
        with contextlib.suppress(Exception):
            id_to_file[fmt.format_state_name(cls.get_full_name())] = rf
            state_files.add(rf)
    fine = state_files - component_files
    return {i: f for i, f in id_to_file.items() if f in fine}, fine


def used_state_files(
    output_code: str,
    memo_components: object,
    id_to_file: dict[str, Path],
) -> set[Path]:
    """Return the fine-grained state files a compiled page depends on.

    Stateful subtrees are auto-memoized into separate components, so a page's
    own ``output_code`` may not name the state it uses; the state lives in the
    memo components it owns (its ``memo_contributions``). Each stateful memo
    is owned by exactly one page, which regenerates it whenever it recompiles,
    so scanning ``output_code`` plus the page's own memo components captures the
    full dependency set. If a memo can't be introspected, depend on every fine
    state file.

    Args:
        output_code: The page's compiled JS.
        memo_components: The page's own memo component subtrees (renderable).
        id_to_file: The state-context identifier -> file index.

    Returns:
        The set of fine-grained state files this page depends on.
    """
    chunks = [output_code or ""]
    try:
        chunks.extend(str(comp.render()) for comp in memo_components)  # type: ignore[attr-defined]
    except Exception:
        return set(id_to_file.values())  # conservative: depend on all
    found: set[Path] = set()
    for chunk in chunks:
        for ident in STATE_CONTEXT_RE.findall(chunk):
            if ident in id_to_file:
                found.add(id_to_file[ident])
    return found


def page_dependency_files(
    page_ctx: PageContext,
    component: BaseComponent | object,
    state_index: dict[str, Path],
    root: Path | None = None,
) -> set[str]:
    """Return the full set of source files a compiled page depends on.

    The union of: the page's own defining module, the files read while it was
    evaluated (markdown/data, via the read recorder), the component modules in
    its rendered tree, and the fine-grained state files it references. A change
    to any file *outside* this set cannot change the page's output, except the
    genuinely-global inputs tracked by :func:`global_epoch` and route additions
    (shared nav). This is the dependency set that makes invalidation precise.

    Args:
        page_ctx: The compiled page context (tree, output, recorded reads).
        component: The page's component/callable (for its defining module).
        state_index: The state-context identifier -> file index.
        root: Project root; only files under it are included. Defaults to cwd.

    Returns:
        The set of resolved dependency file path strings.
    """
    root = (root or Path.cwd()).resolve()
    files: set[Path] = set()
    files |= component_module_files(page_ctx.root_component, root)
    files |= used_state_files(
        page_ctx.output_code or "",
        [m.component for m in page_ctx.memo_contributions.values()],
        state_index,
    )
    deps = {str(f) for f in files}
    # Transitive first-party .py imports (captures function-based views/helpers
    # that never appear as nodes in the rendered tree).
    deps |= page_py_dependencies(component, root)
    # Files read while evaluating the page (markdown/data), plus the import
    # closure of any module the page imported at evaluation time: a helper
    # already loaded by an earlier page does not re-execute its own imports
    # under the recorder, so its dependencies come from the graph instead.
    deps |= set(page_ctx.source_files)
    dynamic_py = {f for f in page_ctx.source_files if f.endswith(".py")}
    if dynamic_py:
        deps |= _walk_import_closure(build_import_graph(root), dynamic_py)
    return deps


def page_dependency_entries(
    page_ctx: PageContext,
    component: BaseComponent | object,
    state_index: dict[str, Path],
    hasher: Callable[[str], FileEntry | None],
    files: dict[str, FileEntry],
    root: Path | None = None,
) -> list[str]:
    """Record a page's dependency set into the manifest file table.

    Args:
        page_ctx: The compiled page context.
        component: The page's component/callable.
        state_index: The state-context identifier -> file index.
        hasher: A memoized path -> :func:`file_entry` function.
        files: The manifest file table, extended in place.
        root: Project root. Defaults to cwd.

    Returns:
        The sorted dependency paths that were readable (the page's ``deps``).
    """
    deps: list[str] = []
    for path in sorted(page_dependency_files(page_ctx, component, state_index, root)):
        entry = hasher(path)
        if entry is not None:
            files[path] = entry
            deps.append(path)
    return deps
