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

**Correctness.** The fingerprint hashes *all* source that affects output, so any
edit — a page, a shared component, a state class, ``rxconfig.py`` — changes it
and forces a full recompile. There is no stale output and no per-page partial
skip, deliberately: the compile produces app-wide aggregates (imports, the app
root, memo dedup) from all pages at once, so a correct per-page partial rebuild
must additionally cache each page's contribution to those aggregates. That is
the documented follow-up; the per-page hybrid-key helpers below
(``page_source_fingerprint``, ``state_versions``) are the building blocks for it.
"""

from __future__ import annotations

import contextlib
import hashlib
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


def shared_fingerprint(page_files: set[Path], root: Path | None = None) -> str:
    """Hash all source EXCEPT the given page-module files, plus the Reflex version.

    Changing any shared file (state, shared component, config) bumps this and
    invalidates every page; editing a single page module does not.

    Args:
        page_files: Page-module files to exclude (they're keyed per page).
        root: Project root to scan. Defaults to cwd.

    Returns:
        A hex digest of the shared inputs.
    """
    root = (root or Path.cwd()).resolve()
    hasher = hashlib.sha256()
    hasher.update(f"reflex={_reflex_version()}\x1f".encode())
    for path in _iter_source_files(root):
        if path.resolve() in page_files:
            continue
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            continue
        hasher.update(f"{path.relative_to(root).as_posix()}={digest}\x1f".encode())
    return hasher.hexdigest()


def page_key(component: object, shared_fp: str) -> str:
    """Hybrid per-page key: this page's source + the shared fingerprint.

    Args:
        component: The page component or factory callable.
        shared_fp: The current shared fingerprint.

    Returns:
        A hex digest identifying this page's compiled output inputs.
    """
    return _sha(page_source_fingerprint(component), shared_fp)


#: In-process store: route -> (page_key, cached PageContext, is_stateful).
_PAGE_STORE: dict[str, tuple[str, PageContext, bool]] = {}


def get_cached_page(route: str, key: str) -> tuple[PageContext, bool] | None:
    """Return ``(PageContext, is_stateful)`` for ``route`` iff its key matches.

    Args:
        route: The page route.
        key: The current hybrid key to validate against.

    Returns:
        The cached page context and its stateful flag, or None on miss.
    """
    entry = _PAGE_STORE.get(route)
    if entry is not None and entry[0] == key:
        return entry[1], entry[2]
    return None


def store_page(route: str, key: str, page_ctx: PageContext, is_stateful: bool) -> None:
    """Record a freshly-compiled page context under its key.

    Args:
        route: The page route.
        key: The hybrid key it was compiled under.
        page_ctx: The compiled PageContext to cache.
        is_stateful: Whether the page registered new state during evaluation.
    """
    _PAGE_STORE[route] = (key, page_ctx, is_stateful)


def clear_page_store() -> None:
    """Drop all in-process per-page cache entries."""
    _PAGE_STORE.clear()


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


def state_versions() -> dict[str, str]:
    """Map each state class's full name to a hash of its definition.

    A page's cached entry records which state contexts it used; on the next
    build a state class whose version changed invalidates only its dependents.

    Returns:
        A mapping of state full name to a hash of its field/method signature.
    """
    from reflex.state import BaseState

    versions: dict[str, str] = {}
    seen = set()

    def visit(cls: type) -> None:
        if cls in seen:
            return
        seen.add(cls)
        try:
            fields = sorted(getattr(cls, "get_fields", dict)().keys())
        except Exception:
            fields = []
        methods = sorted(k for k in vars(cls) if callable(vars(cls)[k]))
        versions[getattr(cls, "get_full_name", lambda: cls.__name__)()] = _sha(
            cls.__name__, ",".join(fields), ",".join(methods)
        )
        for sub in cls.__subclasses__():
            visit(sub)

    with contextlib.suppress(Exception):
        visit(BaseState)
    return versions
