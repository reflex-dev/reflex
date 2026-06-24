"""Stack-walking helpers shared between the inspector and console modules.

The two consumers each need a different ``is_framework_frame`` decision (the
inspector skips Reflex packages only; the console additionally skips stdlib
and a few third-party libraries) but share the underlying mechanics: walking
``frame.f_back`` until the predicate flips.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import sys
from collections.abc import Callable, Iterable
from pathlib import Path
from types import FrameType


class _FrameworkFramePredicate:
    """Cached predicate testing whether a filename lives under any root.

    The roots are pulled from ``roots_provider`` on each cache miss, so the
    caller can replace them dynamically (e.g. after a sub-package import)
    and call :meth:`cache_clear` to invalidate prior results.
    """

    __slots__ = ("_cache", "_roots_provider")

    def __init__(self, roots_provider: Callable[[], Iterable[Path]]):
        self._roots_provider = roots_provider
        self._cache: dict[str, bool] = {}

    def __call__(self, filename: str) -> bool:
        cached = self._cache.get(filename)
        if cached is not None:
            return cached
        try:
            path = Path(filename).resolve()
        except OSError:
            self._cache[filename] = True
            return True
        result = any(path.is_relative_to(root) for root in self._roots_provider())
        self._cache[filename] = result
        return result

    def cache_clear(self) -> None:
        """Drop all cached decisions so the next call re-checks the roots."""
        self._cache.clear()


def make_framework_frame_predicate(
    roots_provider: Callable[[], Iterable[Path]],
) -> _FrameworkFramePredicate:
    """Build a cached ``filename -> bool`` predicate over the given roots.

    Args:
        roots_provider: Returns the roots to test against on each cache miss.
            Allows the predicate to track roots that change over time.

    Returns:
        A callable ``(filename) -> bool`` with a ``cache_clear()`` method.
    """
    return _FrameworkFramePredicate(roots_provider)


def is_framework_package(name: str) -> bool:
    """Whether a top-level package name is part of the Reflex framework.

    Args:
        name: A top-level package name as it would appear in ``sys.modules``.

    Returns:
        True for ``reflex``/``reflex_base`` and any ``reflex_components_*``
        distribution; False for anything else.
    """
    if name in ("reflex", "reflex_base"):
        return True
    return name.startswith("reflex_components_")


def _roots_from_sys_modules() -> list[Path]:
    roots: list[Path] = []
    for name, module in list(sys.modules.items()):
        if "." in name or not is_framework_package(name):
            continue
        file = getattr(module, "__file__", None)
        if file is not None:
            roots.append(Path(file).parent.resolve())
    return roots


def _roots_from_distributions() -> list[Path]:
    roots: list[Path] = []
    try:
        distributions = list(importlib.metadata.distributions())
    except Exception:
        return roots

    for dist in distributions:
        try:
            top_level = (dist.read_text("top_level.txt") or "").splitlines()
        except Exception:
            continue
        for raw in top_level:
            top = raw.strip()
            if not top or not is_framework_package(top) or top in sys.modules:
                continue
            try:
                pkg = importlib.import_module(top)
            except Exception:
                continue
            file = getattr(pkg, "__file__", None)
            if file is not None:
                roots.append(Path(file).parent.resolve())
    return roots


def discover_framework_roots() -> tuple[Path, ...]:
    """Find directories belonging to Reflex framework packages.

    Walks already-imported modules in ``sys.modules`` and the installed
    distributions reported by :mod:`importlib.metadata`. A package whose
    name passes :func:`is_framework_package` is included regardless of how
    it was installed (editable, wheel, src layout).

    Returns:
        Resolved, deduplicated paths to every framework package directory.
    """
    return tuple(dict.fromkeys(_roots_from_sys_modules() + _roots_from_distributions()))


def walk_to_first_non_framework_frame(
    start_frame: FrameType | None,
    is_framework_frame: Callable[[str], bool],
) -> FrameType | None:
    """Walk ``frame.f_back`` until ``is_framework_frame`` returns False.

    Args:
        start_frame: The starting frame; the walk includes this frame.
        is_framework_frame: Predicate over ``co_filename``. Callers may pass a
            cached function to avoid resolving the same path repeatedly.

    Returns:
        The first non-framework frame, or ``None`` if no such frame exists in
        the chain.
    """
    frame = start_frame
    while frame is not None:
        if not is_framework_frame(frame.f_code.co_filename):
            return frame
        frame = frame.f_back
    return None
