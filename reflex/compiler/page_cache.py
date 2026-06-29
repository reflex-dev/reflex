"""Per-page dependency graph for the incremental compile cache (flag-gated).

Enabled by ``REFLEX_COMPILE_CACHE``. When off (the default), the compiler
behaves exactly as before.

**A Salsa-style dependency graph.** Each page records the *exact set of source
files it actually read*, so a change invalidates only the pages that depend on it
(not all pages). A page's dependency set is the union of:

- the **transitive first-party ``.py`` import closure** of its defining module
  (``page_py_dependencies`` — captures function-based views and shared helpers
  that never appear as nodes in the rendered tree, e.g. a ``def hero()`` view, so
  editing one invalidates exactly the pages whose closure imports it),
- the **source files read while evaluating it** (markdown/data — captured by
  ``record_reads`` via the per-page read recorder; this is what lets editing one
  ``.md`` doc page recompile only that page),
- the **component modules in its rendered tree** (``component_module_files`` —
  belt-and-suspenders for components injected at runtime rather than statically
  imported),
- the **fine-grained state files** it references (``used_state_files``).

A page is unchanged iff every file in its dependency set is byte-unchanged and
the small genuinely-global ``global_epoch`` (Reflex version + ``rxconfig`` +
lockfile) is unchanged; adding/removing a route is handled separately (it changes
shared nav). Per-page dependency sets also track files *outside* the project root
(e.g. the docs site reads markdown from a sibling directory), so an
external-source edit still invalidates exactly the dependent pages. These content
hashes and dependency sets are what ``reflex/compiler/disk_cache.py`` persists and
compares each compile to recompile only the pages whose source changed.

Two residual gaps the static graph cannot see: runtime ``importlib`` imports and
data files read at *module-import* time (outside the per-page eval window). An
edit reached only through one of those would not invalidate its page; such
patterns are rare in page modules, and a global/version change still forces a
full recompile.
"""

from __future__ import annotations

import builtins
import contextlib
import hashlib
import re
from collections.abc import Callable
from contextvars import ContextVar
from importlib import metadata
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from reflex_base.components.component import BaseComponent
    from reflex_base.plugins import PageContext

#: Directories never worth hashing (build artifacts, deps, caches).
_SKIP_DIRS = {".web", ".venv", "venv", "node_modules", "__pycache__", ".git", "assets"}

#: Genuinely-global files: a change here can affect every page's output, so it
#: bumps ``global_epoch`` rather than any single page's dependency set.
_GLOBAL_FILES = ("rxconfig.py", "reflex.lock", "uv.lock", "package.json")

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


# --- Per-page read tracking (the Salsa "input read" seam) -------------------
# A page's markdown/data dependencies are read lazily while the page is
# evaluated (e.g. ``Path(doc).read_text()`` inside the page callable). We record
# those reads per page so the cache depends on the exact files consumed. Patches
# are installed once (idempotent) and only record while a recording set is active
# on the current task (set by ``record_reads``), so the overhead is a contextvar
# read when no cache is running.

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


def _record_read(path: object) -> None:
    target = _active_reads.get()
    if target is None:
        return
    try:
        resolved = Path(path).resolve()  # type: ignore[arg-type]
    except (OSError, TypeError, ValueError):
        return
    if any(part in _EXCLUDE_PARTS for part in resolved.parts):
        return
    root = _recorder_root
    under_root = root is not None and root in resolved.parents
    if not under_root and resolved.suffix.lower() not in _CONTENT_SUFFIXES:
        return
    target.add(str(resolved))


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
    _recorder_root = (root or Path.cwd()).resolve()

    from reflex_base.plugins import compiler as _bc

    _bc.page_source_recorder = record_reads

    if _patched:
        return
    _patched = True

    orig_read_text = Path.read_text
    orig_read_bytes = Path.read_bytes
    orig_open = builtins.open

    def read_text(self: Path, *args: object, **kwargs: object):
        _record_read(self)
        return orig_read_text(self, *args, **kwargs)  # type: ignore[arg-type]

    def read_bytes(self: Path):
        _record_read(self)
        return orig_read_bytes(self)

    def open_(file: object, mode: str = "r", *args: object, **kwargs: object):
        if "r" in mode and not ("w" in mode or "a" in mode or "x" in mode):
            _record_read(file)
        return orig_open(file, mode, *args, **kwargs)  # type: ignore[arg-type]

    Path.read_text = read_text  # type: ignore[method-assign,assignment]
    Path.read_bytes = read_bytes  # type: ignore[method-assign,assignment]
    builtins.open = open_  # type: ignore[assignment]


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


def global_epoch(root: Path | None = None) -> str:
    """Fingerprint the genuinely-global inputs (Reflex version + config/lockfiles).

    These can affect every page's output but belong to no single page, so they
    gate the whole cache rather than any one page's dependency set. Kept small on
    purpose — per-file edits flow through per-page dependency sets instead.

    Args:
        root: Project root. Defaults to cwd.

    Returns:
        A hex digest of the global inputs.
    """
    root = (root or Path.cwd()).resolve()
    parts: list[str] = [f"reflex={_reflex_version()}"]
    for name in _GLOBAL_FILES:
        path = root / name
        try:
            parts.append(f"{name}={hashlib.sha256(path.read_bytes()).hexdigest()}")
        except OSError:
            parts.append(f"{name}=<absent>")
    return _sha(*parts)


# In-process per-page cache. Each page is keyed by the genuinely-global epoch
# plus the content hashes of its exact dependency set, so editing one file
# misses only the pages that depend on it. Contributions to the app-wide
# aggregates include live Python objects (root_component, memo defs), so the
# store is in-process only.


def _module_file(component: object) -> Path | None:
    import sys

    mod = sys.modules.get(getattr(component, "__module__", "") or "")
    file = getattr(mod, "__file__", None)
    return Path(file) if file else None


def page_module_files(components: object) -> set[Path]:
    """Resolve the set of module files that define the given page components.

    Args:
        components: An iterable of page component callables/objects.

    Returns:
        The set of resolved module file paths.
    """
    files = set()
    for comp in components:  # type: ignore[attr-defined]
        f = _module_file(comp)
        if f is not None:
            files.add(f.resolve())
    return files


def component_module_files(
    root_component: object, root: Path | None = None
) -> set[Path]:
    """Resolve the first-party module files of every component in a tree.

    Walks the rendered component tree and collects the defining module file of
    each component class under ``root``. This is the precise, barrel-immune way
    (vs. static imports) to capture which shared views/templates a page renders:
    editing one invalidates exactly the pages whose tree contains it.

    Args:
        root_component: The page's root component (its rendered tree).
        root: Project root; only files under it are returned. Defaults to cwd.

    Returns:
        The set of resolved first-party module files the tree depends on.
    """
    root = (root or Path.cwd()).resolve()
    files: set[Path] = set()
    seen: set[int] = set()
    stack: list[object] = [root_component]
    while stack:
        comp = stack.pop()
        if id(comp) in seen:
            continue
        seen.add(id(comp))
        f = _module_file(type(comp))
        if f is not None:
            rf = f.resolve()
            if root in rf.parents:
                files.add(rf)
        children = getattr(comp, "children", None)
        if children:
            stack.extend(children)
    return files


#: Cache of the first-party import graph, keyed by project root.
_import_graph_cache: dict[Path, dict[str, set[str]]] = {}


def _resolve_module_file(name: str) -> str | None:
    import sys

    mod = sys.modules.get(name)
    file = getattr(mod, "__file__", None)
    return str(Path(file).resolve()) if file else None


def _import_from_targets(node: object, modname: str) -> list[str]:
    """Resolve a ``from ... import ...`` node to candidate module names.

    Handles relative imports via the importing module's package. Returns the
    base module and each ``base.name`` (a name may be a submodule or an attribute
    — both candidates are resolved against ``sys.modules`` by the caller).

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


def build_import_graph(root: Path | None = None) -> dict[str, set[str]]:
    """Build the first-party import graph (file -> files it imports).

    Parses every already-imported first-party module's source for ``import`` and
    ``from`` statements and resolves them to files under ``root`` via
    ``sys.modules``. Cached per root for the duration of the process. This is the
    sound basis for per-page ``.py`` dependencies: a function (e.g. a view like
    ``hero()``) can only affect a page if its module is transitively imported by
    the page's module, so it appears in the page's import closure even though it
    is never a node in the rendered tree.

    Args:
        root: Project root. Defaults to cwd.

    Returns:
        A mapping of resolved file path -> the set of first-party files it imports.
    """
    import ast
    import sys

    root = (root or Path.cwd()).resolve()
    cached = _import_graph_cache.get(root)
    if cached is not None:
        return cached

    file_to_mod: dict[str, str] = {}
    for name, mod in list(sys.modules.items()):
        file = getattr(mod, "__file__", None)
        if not file:
            continue
        rf = Path(file).resolve()
        if root in rf.parents:
            file_to_mod[str(rf)] = name

    graph: dict[str, set[str]] = {}
    for file, modname in file_to_mod.items():
        deps: set[str] = set()
        try:
            tree = ast.parse(Path(file).read_bytes())
        except (OSError, SyntaxError, ValueError):
            graph[file] = deps
            continue
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = _import_from_targets(node, modname)
            for n in names:
                target = _resolve_module_file(n)
                if target is not None and target in file_to_mod:
                    deps.add(target)
        graph[file] = deps
    _import_graph_cache[root] = graph
    return graph


def clear_import_graph() -> None:
    """Drop the cached import graph (e.g. after modules are reloaded)."""
    _import_graph_cache.clear()


def page_py_dependencies(
    component: BaseComponent | object, root: Path | None = None
) -> set[str]:
    """Return the transitive first-party ``.py`` files a page's code depends on.

    Starts from the page callable's *real* defining file (``__code__`` filename,
    which is correct even when ``__module__`` was reassigned, as the docs app does
    for generated doc pages) plus its module file, and walks the import graph.
    Captures function-based views and shared helpers that the rendered-tree walk
    cannot see.

    Args:
        component: The page component or callable.
        root: Project root. Defaults to cwd.

    Returns:
        The set of resolved first-party ``.py`` dependency file paths.
    """
    root = (root or Path.cwd()).resolve()
    graph = build_import_graph(root)

    start: set[str] = set()
    code = getattr(component, "__code__", None)
    filename = getattr(code, "co_filename", None)
    if filename:
        rf = Path(filename).resolve()
        if root in rf.parents:
            start.add(str(rf))
    own = _module_file(component)
    if own is not None:
        rf = own.resolve()
        if root in rf.parents:
            start.add(str(rf))

    seen: set[str] = set()
    stack = list(start)
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(graph.get(cur, ()))
    return seen


def make_hasher() -> Callable[[str], str | None]:
    """Return a content-hasher that memoizes each path within one compile.

    Shared component files appear in many pages' dependency sets; hashing each
    file at most once keeps per-page validation cheap.

    Returns:
        A function mapping a path string to its content hash (None if unreadable).
    """
    cache: dict[str, str | None] = {}

    def hasher(path: str) -> str | None:
        if path not in cache:
            try:
                cache[path] = hashlib.sha256(Path(path).read_bytes()).hexdigest()
            except OSError:
                cache[path] = None
        return cache[path]

    return hasher


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
    root = (root or Path.cwd()).resolve()
    from reflex_base.components.component import Component
    from reflex_base.utils import format as fmt

    from reflex.state import BaseState

    def under_root(comp: object) -> Path | None:
        f = _module_file(comp)
        if f is None:
            return None
        rf = f.resolve()
        return rf if root in rf.parents else None

    component_files = {rf for cls in _subclasses(Component) if (rf := under_root(cls))}
    id_to_file: dict[str, Path] = {}
    state_files: set[Path] = set()
    for cls in _subclasses(BaseState):
        rf = under_root(cls)
        if rf is None:
            continue
        with contextlib.suppress(Exception):
            id_to_file[fmt.format_state_name(cls.get_full_name())] = rf
            state_files.add(rf)
    fine = state_files - component_files
    return {i: f for i, f in id_to_file.items() if f in fine}, fine


def file_hashes(files: set[Path]) -> dict[str, str]:
    """Map each file (as a string) to a hash of its current content.

    Args:
        files: The files to hash.

    Returns:
        A mapping of file path string to content hash.
    """
    out: dict[str, str] = {}
    for f in files:
        with contextlib.suppress(OSError):
            out[str(f)] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out


def used_state_files(
    output_code: str,
    memo_components: object,
    id_to_file: dict[str, Path],
) -> set[Path]:
    """Return the fine-grained state files a compiled page depends on.

    Stateful subtrees are auto-memoized into separate components, so a page's
    own ``output_code`` may not name the state it uses — the state lives in the
    memo components it *owns* (its ``memo_contributions``). Each stateful memo
    is owned by exactly one page, which regenerates it whenever it recompiles,
    so scanning ``output_code`` plus the page's own memo components captures the
    full dependency set. If a memo can't be introspected, depend on every fine
    state file (conservative — never stale).

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
    # Files read while evaluating the page (markdown/data).
    deps |= set(page_ctx.source_files)
    return deps


def page_dependency_hashes(
    page_ctx: PageContext,
    component: BaseComponent | object,
    state_index: dict[str, Path],
    hasher: Callable[[str], str | None],
    root: Path | None = None,
) -> dict[str, str]:
    """Hash a page's dependency set into a ``{path: hash}`` map.

    Args:
        page_ctx: The compiled page context.
        component: The page's component/callable.
        state_index: The state-context identifier -> file index.
        hasher: A memoized path -> content-hash function (see :func:`make_hasher`).
        root: Project root. Defaults to cwd.

    Returns:
        ``{path: content_hash}`` for every readable dependency file.
    """
    out: dict[str, str] = {}
    for path in page_dependency_files(page_ctx, component, state_index, root):
        digest = hasher(path)
        if digest is not None:
            out[path] = digest
    return out


def deps_unchanged(
    dep_hashes: dict[str, str], hasher: Callable[[str], str | None]
) -> bool:
    """Whether every file in a stored dependency set still has the same content.

    Args:
        dep_hashes: A page's stored ``{path: hash}`` dependency map.
        hasher: A memoized path -> content-hash function.

    Returns:
        True iff every dependency file is byte-unchanged.
    """
    return all(hasher(path) == digest for path, digest in dep_hashes.items())
