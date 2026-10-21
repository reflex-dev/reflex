"""Per-page dependency discovery for the incremental compile cache.

Each page records the first-party Python import closure of its page callable,
files read during page evaluation, component modules in its rendered tree, and
fine-grained state files it references. ``disk_cache`` persists hashes of that
set so only pages whose dependencies changed need to be recompiled.

Reads are tracked through ``open``, ``io.open``, ``Path.open``,
``Path.read_text``/``read_bytes``, ``tokenize.open`` (``linecache`` and
``inspect.getsource``) and ``io.open_code`` (``pkgutil.get_data``), on the
thread that evaluates the page. A page whose output depends on anything else
(a read from a C extension or a worker thread, the environment, the clock, a
directory listing, a subprocess) calls :func:`mark_volatile` while it
evaluates, and is then recompiled by every compile.
"""

from __future__ import annotations

import ast
import builtins
import contextlib
import dataclasses
import functools
import hashlib
import importlib
import importlib.util
import io
import os
import re
import sys
import time
import tokenize
from collections.abc import Callable, Iterable, Mapping, Sequence
from contextvars import ContextVar
from importlib import metadata
from pathlib import Path
from typing import TYPE_CHECKING

from reflex_base import constants
from reflex_base.environment import environment

if TYPE_CHECKING:
    from reflex_base.components.component import BaseComponent
    from reflex_base.plugins import PageContext

#: A manifest file-table entry: ``[content sha256, st_mtime_ns, st_size]``, or
#: :data:`ABSENT_ENTRY` for a dependency that did not exist, or
#: :data:`RACY_ENTRY` for one that changed while the compile ran.
FileEntry = list

#: The file-table entry of a dependency that was absent when recorded. It is
#: unchanged while the file stays absent.
ABSENT_ENTRY: FileEntry = ["<absent>"]

#: The file-table entry of a dependency modified at or after the compile
#: started (the racy-git rule): the content the compile read is unknown, so
#: the next compile always counts the file as changed and records it afresh.
RACY_ENTRY: FileEntry = ["<racy>", -1, -1]

#: The dependency a volatile page records (see :func:`mark_volatile`). It has
#: no file-table entry, so the page misses on every compile.
VOLATILE_DEP = "<volatile>"

#: Genuinely-global files: a change here can affect every page's output, so it
#: is a global input rather than part of any single page's dependency set.
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


def _reflex_version() -> str:
    """Return the installed Reflex version.

    Returns:
        The version, or ``unknown`` when the package metadata is missing.
    """
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


def _containing_root(path: Path, roots: Iterable[Path]) -> Path | None:
    """Find the root that contains (or is) ``path``.

    Compares path strings: this runs for every import and read under a
    recorder, and ``root in path.parents`` builds a Path per ancestor.

    Args:
        path: Absolute path to test.
        roots: Absolute root paths.

    Returns:
        The first root containing ``path``, or None.
    """
    path_str = str(path)
    for root in roots:
        root_str = str(root)
        if path_str == root_str or path_str.startswith(
            root_str if root_str.endswith(os.sep) else root_str + os.sep
        ):
            return root
    return None


def _under_any(path: Path, roots: Iterable[Path]) -> bool:
    """Whether ``path`` is nested below (or is) one of ``roots``.

    Args:
        path: Absolute path to test.
        roots: Absolute root paths.

    Returns:
        True when some root contains ``path``.
    """
    return _containing_root(path, roots) is not None


# A page's markdown/data dependencies are read lazily while the page is
# evaluated. Track those reads only while ``record_reads`` is active, so the
# idle overhead is one contextvar read.

_active_reads: ContextVar[set[str] | None] = ContextVar("_active_reads", default=None)
_patched = False
_recorder_root: Path | None = None
#: The first-party roots of ``_recorder_root``, resolved once per root.
_recorder_roots: tuple[Path, ...] = ()
#: ``time.time_ns()`` when the current compile started importing the app.
#: A dependency modified at or after it is recorded as :data:`RACY_ENTRY`.
_compile_start_ns: int | None = None

#: Path parts that mark a dependency/build location whose files are never a
#: page's own source dependency (a change there flows through the version or
#: the global inputs). Tested against the parts below the first-party root a
#: file is under, so a project living in a directory of such a name is not
#: excluded wholesale; a file outside every root is tested by its full path.
_EXCLUDE_PARTS = frozenset({
    constants.Dirs.WEB,
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".git",
    "site-packages",
    "dist-packages",
})


def _excluded(path: Path, roots: tuple[Path, ...]) -> bool:
    """Whether ``path`` lies in a dependency/build location.

    Args:
        path: Absolute path to test.
        roots: The first-party roots.

    Returns:
        True when a part of the path (below its root, if any) names an
        excluded directory.
    """
    parts = path.parts
    if (root := _containing_root(path, roots)) is not None:
        parts = parts[len(root.parts) :]
    return not _EXCLUDE_PARTS.isdisjoint(parts)


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

#: Maps a first-party module file to the files code in it read under a
#: recorder, whichever page (or the app import) was running. A read behind a
#: shared cache (``functools.cache``, a module-level loader) happens once per
#: process, for the first caller only, so a page depends on the reads of every
#: module in its import closure, not only on the reads its own evaluation
#: performed. The over-approximation is safe.
_module_reads: dict[str, set[str]] = {}
_THIS_FILE = __file__


def forget_module_reads() -> None:
    """Drop the reads attributed to modules (before first-party code reloads)."""
    _module_reads.clear()


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


def _reading_module_file() -> str | None:
    """Find the first-party module whose code performed the current read.

    Walks the stack from the read hook's caller up to the first frame whose
    code lives in a first-party module file, so a read made by a library on
    a page's behalf is attributed to the page's code.

    Returns:
        The resolved module file, or None when no first-party code is on the
        stack.
    """
    frame = sys._getframe(2)
    while frame is not None:
        file = frame.f_code.co_filename
        if file != _THIS_FILE and (module_file := _recordable_module_file(file)):
            return module_file
        frame = frame.f_back
    return None


def _record_read(path: object) -> None:
    """Add a first-party file read to the active read set, if any.

    The read is also attributed to the first-party module that performed it
    (see :data:`_module_reads`).

    Args:
        path: The path the code read.
    """
    target = _active_reads.get()
    if target is None:
        return
    with _suspend_tracking():
        try:
            resolved = Path(path).resolve()  # type: ignore[arg-type]
        except (OSError, TypeError, ValueError):
            return
        if _excluded(resolved, _recorder_roots):
            return
        if (
            not _under_any(resolved, _recorder_roots)
            and resolved.suffix.lower() not in _CONTENT_SUFFIXES
        ):
            return
        read = str(resolved)
        target.add(read)
        if (module_file := _reading_module_file()) is not None:
            _module_reads.setdefault(module_file, set()).add(read)


def mark_volatile() -> None:
    """Make the page being evaluated recompile on every compile.

    For a page whose output depends on an input the cache cannot see: a read
    made by a C extension or on another thread, an environment variable, the
    clock, a directory listing, a subprocess. A no-op outside a compile that
    records dependencies.
    """
    if (target := _active_reads.get()) is not None:
        target.add(VOLATILE_DEP)


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

        roots = _recorder_roots
        resolved_str = None
        if not _excluded(path, roots) and (
            _under_any(path, roots) or not _is_python_install_file(path)
        ):
            try:
                resolved = path.resolve()
            except (OSError, TypeError, ValueError):
                pass
            else:
                if _under_any(resolved, roots) and not _excluded(resolved, roots):
                    resolved_str = str(resolved)
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
    parent = name
    while "." in parent:
        parent = parent.rsplit(".", 1)[0]
        if (module := sys.modules.get(parent)) is not None:
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

    Idempotent. Patches the read entry points named in the module docstring
    and the import functions to record reads and imported module files (only
    while a recording set is active) and points the reflex-base compile loop
    at :func:`record_reads`. Called when an incremental cache flag is on; a
    no-op to the compile otherwise.

    Args:
        root: Project root; only reads under it are recorded. Defaults to cwd.
    """
    global _patched, _recorder_root, _recorder_roots
    resolved_root = (root or Path.cwd()).resolve()
    if _recorder_root != resolved_root:
        _module_file_cache.clear()
        _module_reads.clear()
        _recorder_roots = first_party_roots(resolved_root)
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
    orig_open_code = io.open_code
    orig_tokenize_open = tokenize.open
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

    # ``importlib`` loaders (``pkgutil.get_data``) read through the C module.
    def open_code(path: str):
        _record_read(path)
        return orig_open_code(path)

    # ``linecache`` (``inspect.getsource``) opens source through ``tokenize``,
    # which bound ``builtins.open`` when it was imported.
    def tokenize_open(filename: object):
        _record_read(filename)
        return orig_tokenize_open(filename)  # type: ignore[arg-type]

    def import_(
        name: str,
        globals_: dict[str, object] | None = None,
        locals_: dict[str, object] | None = None,
        fromlist: Sequence[str] | None = (),
        level: int = 0,
    ):
        result = orig_import(name, globals_, locals_, fromlist, level)
        if (target := _active_reads.get()) is not None:
            absolute = _absolute_import_name(name, globals_, level)
            _record_imported_modules(absolute, result, target, fromlist)
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
    io.open = open_  # type: ignore[assignment]
    io.open_code = open_code
    # ``importlib`` loaders call ``open_code`` on the C module object.
    setattr(sys.modules["_io"], "open_code", open_code)  # noqa: B010
    tokenize.open = tokenize_open  # type: ignore[assignment]
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

    Also marks the start of the compile, for the racy-edit rule of
    :func:`file_entry`: everything the compile reads is read after this.

    Args:
        root: Project root. Defaults to cwd.

    Yields:
        None.
    """
    global _compile_start_ns
    root = (root or Path.cwd()).resolve()
    _compile_start_ns = time.time_ns()
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


def _is_racy(mtime_ns: int) -> bool:
    """Whether a file modified at ``mtime_ns`` may have changed during the compile.

    A file modified at or after the compile started may hold other content
    than the compile read. A whole-second timestamp comes from a file system
    with coarse timestamps, where a change in the compile's first second is
    indistinguishable from one just before it.

    Args:
        mtime_ns: The file's modification time.

    Returns:
        True when the content the compile read cannot be vouched for.
    """
    if (start := _compile_start_ns) is None:
        return False
    if mtime_ns % 1_000_000_000 == 0:
        start -= start % 1_000_000_000
    return mtime_ns >= start


def _is_page_registration(statement: ast.stmt) -> bool:
    """Whether a top-level statement is an ``<app>.add_page(...)`` call.

    Args:
        statement: A module-level statement.

    Returns:
        True for an ``add_page`` call statement.
    """
    return (
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Call)
        and isinstance(statement.value.func, ast.Attribute)
        and statement.value.func.attr == "add_page"
    )


def _loaded_names(nodes: Iterable[ast.AST]) -> set[str]:
    """Collect the names the given syntax trees read.

    Args:
        nodes: The syntax trees.

    Returns:
        Every name loaded anywhere within them.
    """
    return {
        node.id
        for tree in nodes
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }


#: Separates a module file from a module-level function name in a dependency
#: on the parts of the module that function can read (see
#: :func:`function_slice_digest`).
SLICE_SEPARATOR = "::"

#: Names through which code reaches module globals, or the module's own
#: source text or line numbers, that no syntax tree names: a slice reading
#: any of them depends on the whole module file.
_DYNAMIC_GLOBAL_NAMES = frozenset({
    "globals",
    "vars",
    "locals",
    "eval",
    "exec",
    "__import__",
    "sys",
    "inspect",
    "linecache",
    "tokenize",
    "getsource",
    "getsourcelines",
    "getsourcefile",
})

#: Decorators (``<module>.<name>``) that keep the function they wrap to
#: themselves at import time.
_INERT_DECORATORS = frozenset({
    ("rx", "page"),
    ("rx", "memo"),
    ("reflex", "page"),
    ("reflex", "memo"),
    ("functools", "cache"),
    ("functools", "lru_cache"),
})


def dep_file(dep: str) -> str:
    """Return the file a dependency reads.

    Args:
        dep: A file path, or a function slice (``<file>::<function>``).

    Returns:
        The file path.
    """
    file, separator, _ = dep.rpartition(SLICE_SEPARATOR)
    return file if separator else dep


@dataclasses.dataclass(frozen=True, slots=True)
class _ModulePart:
    """One top-level statement of a module, as a slice sees it."""

    # The statement's syntax tree and the names it reads.
    dump: str
    loads: frozenset[str]
    # A function or class: its name, and the parts that run at import time
    # (decorators, defaults, bases) with the names they read.
    name: str | None = None
    is_class: bool = False
    header: str = ""
    header_loads: frozenset[str] = frozenset()
    # An import: each bound name (``*`` for a star import) and its syntax tree.
    aliases: tuple[tuple[str, str], ...] = ()


def _is_inert_decorator(decorator: ast.expr) -> bool:
    """Whether a decorator keeps the function it wraps to itself.

    Args:
        decorator: The decorator expression.

    Returns:
        True for a known decorator such as ``rx.page`` or ``functools.cache``.
    """
    if isinstance(decorator, ast.Call):
        decorator = decorator.func
    return (
        isinstance(decorator, ast.Attribute)
        and isinstance(decorator.value, ast.Name)
        and (decorator.value.id, decorator.attr) in _INERT_DECORATORS
    )


def _module_part(statement: ast.stmt) -> _ModulePart:
    """Describe one top-level statement for slicing.

    Args:
        statement: The statement.

    Returns:
        Its slice description.
    """
    if isinstance(statement, (ast.Import, ast.ImportFrom)):
        origin = (
            f"{statement.module}:{statement.level}:"
            if isinstance(statement, ast.ImportFrom)
            else ""
        )
        return _ModulePart(
            dump="",
            loads=frozenset(),
            aliases=tuple(
                (
                    (alias.asname or alias.name).partition(".")[0],
                    origin + ast.dump(alias),
                )
                for alias in statement.names
            ),
        )
    dump = ast.dump(statement)
    loads = frozenset(_loaded_names([statement]))
    # A decorator other than the inert ones may hand the function to code
    # that runs at import (a registry), so it counts as import-time code.
    if isinstance(
        statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    ) and all(_is_inert_decorator(d) for d in statement.decorator_list):
        header: list[ast.expr] = list(statement.decorator_list)
        if isinstance(statement, ast.ClassDef):
            header.extend(statement.bases)
            header.extend(keyword.value for keyword in statement.keywords)
        else:
            header.extend(statement.args.defaults)
            header.extend(d for d in statement.args.kw_defaults if d is not None)
        return _ModulePart(
            dump=dump,
            loads=loads,
            name=statement.name,
            is_class=isinstance(statement, ast.ClassDef),
            header="".join(ast.dump(node) for node in header),
            header_loads=frozenset(_loaded_names(header)),
        )
    return _ModulePart(dump=dump, loads=loads)


#: File -> (stat key, parts) for the modules sliced in this process.
_module_parts_cache: dict[str, tuple[tuple[int, int], list[_ModulePart]]] = {}


def _module_parts(path: str) -> list[_ModulePart] | None:
    """Parse a module into slice parts, leaving out its page registrations.

    Args:
        path: The module file.

    Returns:
        The parts in source order, or None when the file cannot be read or
        parsed.
    """
    key = _stat_key(path)
    cached = _module_parts_cache.get(path)
    if key is not None and cached is not None and cached[0] == key:
        return cached[1]
    try:
        tree = ast.parse(Path(path).read_bytes())
    except (OSError, SyntaxError, ValueError):
        return None
    parts = [_module_part(s) for s in tree.body if not _is_page_registration(s)]
    if key is not None:
        _module_parts_cache[path] = (key, parts)
    return parts


def _definition_closure(
    definitions: Mapping[str, Sequence[_ModulePart]], starts: Iterable[str]
) -> set[str]:
    """Name the definitions reachable from ``starts`` through the names they read.

    Args:
        definitions: The module's definitions by name.
        starts: The names to start from.

    Returns:
        The reachable definition names.
    """
    closure: set[str] = set()
    stack = [name for name in starts if name in definitions]
    while stack:
        name = stack.pop()
        if name in closure:
            continue
        closure.add(name)
        stack.extend(
            load
            for part in definitions[name]
            for load in part.loads
            if load in definitions and load not in closure
        )
    return closure


def _sliced_texts(part: _ModulePart, closure: set[str]) -> list[str]:
    """Return what one module part adds to a slice.

    Args:
        part: The part.
        closure: The definitions in the slice.

    Returns:
        The texts to digest.
    """
    if part.aliases:
        # Every import counts: importing a module runs it, and that can
        # change what any code in this module sees.
        return [dump for _, dump in part.aliases]
    if part.name is None or part.name in closure:
        return [part.dump]
    return [part.header] if part.header else []


def _slice_digest(parts: Sequence[_ModulePart], seeds: Iterable[str]) -> str | None:
    """Digest the parts of a module that code starting at ``seeds`` can read.

    That is every statement that runs at import (imports included), the
    import-time parts of every definition, and the whole definitions named
    (transitively) by those or by ``seeds``. Like a dependency across modules,
    a call-time mutation of a shared object is not tracked.

    Args:
        parts: The module's parts (see :func:`_module_parts`).
        seeds: The definition names to start from.

    Returns:
        The hex digest, or None when the code reaches module globals or the
        module's own source by a computed name, so only the whole file is a
        safe dependency.
    """
    definitions: dict[str, list[_ModulePart]] = {}
    always: set[str] = set()
    for part in parts:
        if part.name is not None:
            definitions.setdefault(part.name, []).append(part)
            always |= part.header_loads
        else:
            always |= part.loads
    closure = _definition_closure(definitions, (*seeds, *always))
    used = always.union(*(part.loads for name in closure for part in definitions[name]))
    if not used.isdisjoint(_DYNAMIC_GLOBAL_NAMES):
        return None
    digest = hashlib.sha256()
    for part in parts:
        for text in _sliced_texts(part, closure):
            digest.update(text.encode())
            digest.update(b"\n")
    return digest.hexdigest()


def _class_names(parts: Sequence[_ModulePart]) -> list[str]:
    """Name a module's top-level classes.

    Args:
        parts: The module's parts.

    Returns:
        The class names.
    """
    return [part.name for part in parts if part.name is not None and part.is_class]


def function_slice_digest(path: str, name: str) -> str | None:
    """Digest the parts of a module a module-level function can read.

    Every class counts: a page reaches the states and components of its own
    module through its rendered tree, not only through names it reads.

    Args:
        path: The module file.
        name: The function's name.

    Returns:
        The digest, or None when the file cannot be parsed, defines no such
        module-level function or class, or reaches its globals or source by
        a computed name (see :func:`_slice_digest`).
    """
    parts = _module_parts(path)
    if parts is None or not any(part.name == name for part in parts):
        return None
    return _slice_digest(parts, (name, *_class_names(parts)))


def entrypoint_digest(path: str) -> str | None:
    """Digest the app entry module apart from its pages.

    Left out are top-level ``<app>.add_page(...)`` statements and the page
    functions defined in the module (each page tracks its own slice, see
    :func:`function_slice_digest`). Every import counts, a page's included:
    importing a module runs it. Class bodies run at import, so every class
    counts. Also left out is what the syntax tree never holds (comments,
    formatting). Two versions with the same digest differ only in their
    pages, which the compile cache compares page by page; any other edit can
    change every page.

    Args:
        path: The entry module's file.

    Returns:
        The digest, or None when the file cannot be read or parsed, or
        reaches its globals or source by a computed name.
    """
    parts = _module_parts(path)
    if parts is None:
        return None
    return _slice_digest(parts, _class_names(parts))


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


def global_input_paths(
    root: Path | None = None, *, pages: Sequence[object] | None = None
) -> dict[str, str]:
    """Map each file-backed global input label to its path.

    These can affect every page's output but belong to no single page, so they
    gate the whole cache rather than any one page's dependency set: the
    config/lockfiles and the app-level config files, i.e. the app entrypoint
    module plus the config-only modules it imports (theme, app-wraps,
    stylesheets, head components; see :func:`app_dependency_files`). Kept small
    on purpose; per-file edits flow through per-page dependency sets instead.
    The manifest stores these labels with their paths and keeps the content
    entries in its file table, so validation is stat-first like page deps.

    Args:
        root: Project root. Defaults to cwd.
        pages: The current page definitions, used as barriers so page modules
            (tracked per page) are excluded from the app-level config files.

    Returns:
        ``{label: path}`` for every global input except the Reflex version.
    """
    root = (root or Path.cwd()).resolve()
    paths = {name: str(root / name) for name in _GLOBAL_FILES}
    paths.update({f"app:{p}": p for p in app_dependency_files(pages, root)})
    return paths


def _module_file(component: object) -> Path | None:
    """Return the file of the module an object belongs to.

    Args:
        component: The object.

    Returns:
        The module file, or None.
    """
    mod = sys.modules.get(getattr(component, "__module__", "") or "")
    file = getattr(mod, "__file__", None)
    return Path(file) if file else None


#: Component/state class and roots -> its first-party module file (or None).
#: A rendered tree has tens of thousands of nodes but few distinct classes,
#: and a class's module never moves; resolving per node dominated the
#: dependency walk. Warmed in the daemon parent so forked children inherit it.
_class_file_cache: dict[tuple[type, tuple[Path, ...]], Path | None] = {}


def _class_module_file(cls: type, roots: tuple[Path, ...]) -> Path | None:
    """Resolve a class's module file when it is first-party.

    Args:
        cls: The component or state class.
        roots: The first-party roots.

    Returns:
        The resolved module file under one of ``roots``, else None.
    """
    key = (cls, roots)
    try:
        return _class_file_cache[key]
    except KeyError:
        pass
    f = _module_file(cls)
    resolved = None
    if f is not None:
        rf = f.resolve()
        if _under_any(rf, roots):
            resolved = rf
    _class_file_cache[key] = resolved
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
    _loaded_first_party_modules(roots[0])


def component_tree_classes(root_component: object) -> set[type]:
    """Collect the class of every component in a rendered tree.

    Args:
        root_component: The page's root component (its rendered tree).

    Returns:
        The distinct component classes.
    """
    classes: set[type] = set()
    seen: set[int] = set()
    stack: list[object] = [root_component]
    while stack:
        comp = stack.pop()
        if id(comp) in seen:
            continue
        seen.add(id(comp))
        classes.add(type(comp))
        children = getattr(comp, "children", None)
        if children:
            stack.extend(children)
    return classes


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
    return {
        rf
        for cls in component_tree_classes(root_component)
        if (rf := _class_module_file(cls, roots)) is not None
    }


#: Cache of the first-party import graph, keyed by project root.
_import_graph_cache: dict[Path, dict[str, set[str]]] = {}


def _resolve_module_file(name: str) -> str | None:
    """Return the resolved file of a loaded module.

    Args:
        name: The dotted module name.

    Returns:
        The resolved file path, or None.
    """
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
        if (resolved := _first_party_module_file(file, roots)) is not None:
            file_to_mod[resolved] = name
    return file_to_mod


@functools.lru_cache(maxsize=8192)
def _first_party_module_file(file: str, roots: tuple[Path, ...]) -> str | None:
    """Resolve a stable module filename once per set of reload roots.

    Args:
        file: The module's source filename.
        roots: Resolved first-party roots.

    Returns:
        The resolved filename if it belongs to a first-party root, else None.
    """
    resolved = Path(file).resolve()
    return str(resolved) if _under_any(resolved, roots) else None


def _import_from_targets(
    node: object, modname: str, *, is_package: bool = False
) -> list[str]:
    """Resolve a ``from ... import ...`` node to candidate module names.

    Handles relative imports via the importing module's package. Returns the
    base module and each ``base.name``. A name may be a submodule or an
    attribute; both candidates are resolved against ``sys.modules`` by the
    caller.

    Args:
        node: An ``ast.ImportFrom`` node.
        modname: The dotted name of the module containing the import.
        is_package: Whether the importing module is a package initializer.

    Returns:
        Candidate dotted module names to resolve.
    """
    if not isinstance(node, ast.ImportFrom):
        return []
    if node.level:  # relative import: walk up from the importing package
        package = modname if is_package else modname.rpartition(".")[0]
        try:
            base = importlib.util.resolve_name(
                "." * node.level + (node.module or ""), package
            )
        except (ImportError, ValueError):
            return []
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
            names.extend(
                _import_from_targets(
                    node, modname, is_package=Path(file).name == "__init__.py"
                )
            )
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
    while isinstance(component, functools.partial):
        component = component.func
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
    :func:`global_input_paths`: editing one forces a full recompile instead of leaving
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
    barriers.discard(start)
    static_deps = _walk_import_closure(graph, {start}, barriers)
    dynamic_deps = _app_import_reads.get(root, set()) - page_deps
    return static_deps | dynamic_deps


def file_entry(path: str) -> FileEntry | None:
    """Read a file once and describe it for the manifest file table.

    Args:
        path: The file path.

    Returns:
        ``[sha256, st_mtime_ns, st_size]``, or None if unreadable. For a
        function slice (see :data:`SLICE_SEPARATOR`), the slice digest and
        the stat of its file. :data:`RACY_ENTRY` for a file modified since
        the compile started (see :func:`_is_racy`).
    """
    file, separator, name = path.rpartition(SLICE_SEPARATOR)
    if separator:
        key = _stat_key(file)
        digest = function_slice_digest(file, name)
        if key is None or digest is None:
            return None
        return RACY_ENTRY if _is_racy(key[0]) else [digest, *key]
    try:
        with Path(path).open("rb") as fh:
            st = os.fstat(fh.fileno())
            digest = hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return None
    if _is_racy(st.st_mtime_ns):
        return RACY_ENTRY
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
            A recorded-absent file is unchanged while it is still absent; a
            racy entry (see :data:`RACY_ENTRY`) always counts as changed.
        """
        cached = self._changed.get(path)
        if cached is not None:
            return cached
        entry = self._files.get(path)
        result = True
        if entry == ABSENT_ENTRY:
            result = SLICE_SEPARATOR in path or Path(path).exists()
        elif entry is not None and entry != RACY_ENTRY and len(entry) == 3:
            key = _stat_key(dep_file(path))
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
    """List a class and every subclass below it.

    Args:
        root_cls: The class to start from.

    Returns:
        The classes, each once.
    """
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
    memo components it uses (its ``memo_uses``), so scanning ``output_code``
    plus those captures the full dependency set. If a memo can't be
    introspected, depend on every fine state file.

    Args:
        output_code: The page's compiled JS.
        memo_components: The memo component subtrees the page uses (renderable).
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
    genuinely-global inputs tracked by :func:`global_input_paths` and route additions
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
        [m.component for m in page_ctx.memo_uses.values()],
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
    # What the modules in the closure read on any page's behalf (a read
    # behind a shared cache happens for the first caller only).
    deps.update(*(_module_reads.get(dep, ()) for dep in list(deps)))
    if (own := _own_function_slice(component, page_ctx.source_files, root)) is not None:
        deps.discard(dep_file(own))
        deps.add(own)
    return deps


def _own_function_slice(
    component: object, source_files: Iterable[str], root: Path
) -> str | None:
    """The slice of its module a page function reads, when that is all it reads.

    A page reaching its module another way (an import cycle, an import or a
    read during evaluation) depends on the whole file.

    Args:
        component: The page component or callable.
        source_files: The files read while the page was evaluated.
        root: Resolved project root.

    Returns:
        The slice dependency (``<file>::<function>``), or None.
    """
    name = getattr(component, "__name__", None)
    files = _component_source_files(component, root)
    if (
        not isinstance(name, str)
        or getattr(component, "__qualname__", None) != name
        or len(files) != 1
    ):
        return None
    (file,) = files
    source_files = set(source_files)
    graph = build_import_graph(root)
    starts = graph.get(file, set()) | {f for f in source_files if f.endswith(".py")}
    if (
        file in source_files
        or file in _walk_import_closure(graph, starts)
        or function_slice_digest(file, name) is None
    ):
        return None
    return f"{file}{SLICE_SEPARATOR}{name}"


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
        The sorted dependency paths, including missing files (the page's ``deps``).
    """
    deps: list[str] = []
    for path in sorted(page_dependency_files(page_ctx, component, state_index, root)):
        if path != VOLATILE_DEP:
            entry = hasher(path)
            files[path] = ABSENT_ENTRY if entry is None else entry
        deps.append(path)
    return deps
