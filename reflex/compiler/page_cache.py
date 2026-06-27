"""Experimental persistent compile cache (flag-gated).

Enabled by ``REFLEX_PERSISTENT_COMPILE_CACHE``. When off (the default), the
compiler behaves exactly as before.

**Tier 1 (implemented here): complete source fingerprint.** When the app's
source (every ``.py``/``.md``/``.mdx`` under the project root) and the installed
Reflex version are unchanged since the last successful compile, the frontend
compile is skipped entirely and the existing ``.web`` output is reused. This
makes "nothing changed" rebuilds — re-run, restart, an unchanged CI job — nearly
free, *content-aware* (today's ``_should_compile`` is only a manual
nocompile-file check).

**Tier 2: in-process per-page cache.** Each page is validated against three
inputs: its own module source (fine — only the edited page misses), the coarse
``shared_fingerprint`` of everything shared except page and pure-state files
(template/component/config edits → all miss), and the content hashes of the
*fine-grained state files* it actually references (a pure-state-module edit
invalidates only the pages that use that state — see ``state_dependency_index``
and ``validate_page``). Cached pages' contributions are re-merged into the
app-wide aggregates by ``compile_app``; the store holds live objects
(``PageContext``), so it is in-process only. ``REFLEX_COMPILE_CACHE_VERIFY``
proves the cache-assisted output matches a full compile and falls back on any
mismatch.
"""

from __future__ import annotations

import contextlib
import hashlib
import re
from importlib import metadata
from pathlib import Path
from typing import TYPE_CHECKING

from reflex.utils import prerequisites

if TYPE_CHECKING:
    from reflex_base.components.component import BaseComponent
    from reflex_base.plugins import PageContext

#: Source extensions whose content affects the compiled output.
SOURCE_SUFFIXES = (".py", ".md", ".mdx")

#: Directories never worth hashing (build artifacts, deps, caches).
_SKIP_DIRS = {".web", ".venv", "venv", "node_modules", "__pycache__", ".git", "assets"}

#: Where the fingerprint of the last successful compile is stored.
_FINGERPRINT_FILE = "compile_fingerprint.txt"

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


def _iter_source_files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        if any(part in _SKIP_DIRS for part in path.relative_to(root).parts[:-1]):
            continue
        if path.suffix in SOURCE_SUFFIXES:
            yield path


def app_source_fingerprint(root: Path | None = None) -> str:
    """Hash all source under ``root`` (cwd by default) + the Reflex version.

    Complete by construction: every file that can change the compiled output is
    included, so a stale skip is impossible.

    Args:
        root: Project root to scan. Defaults to the current working directory.

    Returns:
        A hex digest identifying this exact source + framework state.
    """
    root = (root or Path.cwd()).resolve()
    hasher = hashlib.sha256()
    hasher.update(f"reflex={_reflex_version()}\x1f".encode())
    for path in _iter_source_files(root):
        rel = path.relative_to(root).as_posix()
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            continue
        hasher.update(f"{rel}={digest}\x1f".encode())
    return hasher.hexdigest()


def _fingerprint_path() -> Path:
    return prerequisites.get_web_dir() / _FINGERPRINT_FILE


def has_prior_output() -> bool:
    """Whether a previous compile left usable output to reuse.

    Returns:
        True if a recorded fingerprint and prior .web output both exist.
    """
    web = prerequisites.get_web_dir()
    return _fingerprint_path().exists() and (web / "react-router.config.js").exists()


def is_unchanged(fingerprint: str) -> bool:
    """Whether ``fingerprint`` matches the last successfully recorded compile.

    Args:
        fingerprint: The current source fingerprint to compare.

    Returns:
        True if it matches the recorded one and prior output exists.
    """
    path = _fingerprint_path()
    try:
        return path.read_text().strip() == fingerprint and has_prior_output()
    except OSError:
        return False


def record(fingerprint: str) -> None:
    """Persist ``fingerprint`` as the last successful compile."""
    path = _fingerprint_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(fingerprint)
    except OSError:
        pass  # best-effort: a cache write failure must never break the build.


# --- Tier 2: in-process per-page cache --------------------------------------
# Per-page key = (page-module source fingerprint, shared fingerprint). Fine on
# the page's own source (the frequent dev edit -> only that page misses); coarse
# on everything shared (state, shared components, config, reflex version ->
# every page misses). Contributions to the app-wide aggregates include live
# Python objects (root_component, memo defs), so the store is in-process only.


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


def shared_fingerprint(exclude_files: set[Path], root: Path | None = None) -> str:
    """Hash all source EXCEPT ``exclude_files``, plus the Reflex version.

    ``exclude_files`` is the page-module files (keyed per page) plus the
    fine-grained state files (versioned per file). Editing any *other* shared
    file (template, shared component, config) bumps this and invalidates every
    page; editing a page module or a pure state file does not.

    Args:
        exclude_files: Resolved files handled per-page (not via this fingerprint).
        root: Project root to scan. Defaults to cwd.

    Returns:
        A hex digest of the coarse shared inputs.
    """
    root = (root or Path.cwd()).resolve()
    hasher = hashlib.sha256()
    hasher.update(f"reflex={_reflex_version()}\x1f".encode())
    for path in _iter_source_files(root):
        if path.resolve() in exclude_files:
            continue
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            continue
        hasher.update(f"{path.relative_to(root).as_posix()}={digest}\x1f".encode())
    return hasher.hexdigest()


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


def page_source_fingerprint(component: BaseComponent | object) -> str:
    """Fingerprint a page from its own module source (no build required).

    Args:
        component: The page component or factory callable.

    Returns:
        A hex digest of the page's defining module source.
    """
    import inspect
    import sys

    module_name = getattr(component, "__module__", None)
    parts = [repr(getattr(component, "__qualname__", repr(component)))]
    mod = sys.modules.get(module_name) if module_name else None
    file = getattr(mod, "__file__", None)
    if file and Path(file).exists():
        with contextlib.suppress(OSError):
            parts.append(hashlib.sha256(Path(file).read_bytes()).hexdigest())
    elif callable(component):
        with contextlib.suppress(OSError, TypeError):
            parts.append(inspect.getsource(component))
    return _sha(*parts)


#: route -> (page_source_fp, shared_fp, used_state_hashes, PageContext, is_stateful)
_PAGE_STORE: dict[str, tuple[str, str, dict[str, str], PageContext, bool]] = {}


def validate_page(
    route: str,
    page_source_fp: str,
    shared_fp: str,
    current_state_hashes: dict[str, str],
) -> tuple[PageContext, bool] | None:
    """Return the cached page iff all its inputs are unchanged.

    A page is valid when its own source is unchanged, the coarse shared
    fingerprint is unchanged, and every fine-grained state file it used still
    hashes the same. A state edit therefore only invalidates pages that use it.

    Args:
        route: The page route.
        page_source_fp: The page's current source fingerprint.
        shared_fp: The current coarse shared fingerprint.
        current_state_hashes: Current {state file -> hash} for all fine files.

    Returns:
        ``(PageContext, is_stateful)`` on a valid hit, else None.
    """
    entry = _PAGE_STORE.get(route)
    if entry is None:
        return None
    stored_src, stored_shared, used_hashes, page_ctx, is_stateful = entry
    if stored_src != page_source_fp or stored_shared != shared_fp:
        return None
    for file, digest in used_hashes.items():
        if current_state_hashes.get(file) != digest:
            return None
    return page_ctx, is_stateful


def store_page(
    route: str,
    page_source_fp: str,
    shared_fp: str,
    used_state_hashes: dict[str, str],
    page_ctx: PageContext,
    is_stateful: bool,
) -> None:
    """Record a freshly-compiled page with the inputs it depends on.

    Args:
        route: The page route.
        page_source_fp: The page's source fingerprint.
        shared_fp: The coarse shared fingerprint it compiled under.
        used_state_hashes: {state file -> hash} for the state it referenced.
        page_ctx: The compiled PageContext to cache.
        is_stateful: Whether the page registered new state during evaluation.
    """
    _PAGE_STORE[route] = (
        page_source_fp,
        shared_fp,
        used_state_hashes,
        page_ctx,
        is_stateful,
    )


def clear_page_store() -> None:
    """Drop all in-process per-page cache entries."""
    _PAGE_STORE.clear()
