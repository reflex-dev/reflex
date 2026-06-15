"""Mirror user-app Python module paths into the compiler's ``.web`` output.

The compiler uses these helpers to write each memo's compiled JSX to a path
under ``.web/app_components/`` that mirrors its Python source module, instead of
bundling everything into one file. This module owns the small set of helpers
that:

- Read ``fn.__module__`` and reject framework / synthetic modules.
- Walk the live frame stack as a fallback for entry points that don't take a
  user-supplied callable (notably ``app.add_page(component)`` with a Component
  instance).
- Translate a dotted Python module name into mirrored JSX path segments and
  the corresponding ``$/...`` library specifier consumed by the import system.
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
from collections.abc import Callable
from pathlib import Path

from reflex_base.constants.base import Dirs

# Framework packages: a memo defined in one of these (the package itself or any
# submodule below it) is never mirrored, so we don't emit ``.web/reflex/...``
# files for memos defined inside the framework's own component packages.
_FRAMEWORK_PACKAGES = (
    "reflex",
    "reflex_base",
    "reflex_site_shared",
    "reflex_hosting_cli",
    "reflex_docgen",
)

# Bare-name prefixes matched against the whole module name (no dot boundary),
# covering families of framework packages such as ``reflex_components_radix``.
_FRAMEWORK_NAME_PREFIXES = ("reflex_components_",)


def _is_framework_module(module_name: str) -> bool:
    """Whether ``module_name`` belongs to the framework itself.

    Args:
        module_name: The dotted module name.

    Returns:
        True if the module is part of the framework and should not be
        mirrored under ``.web/``.
    """
    if module_name.startswith(_FRAMEWORK_NAME_PREFIXES):
        return True
    return any(
        module_name == pkg or module_name.startswith(pkg + ".")
        for pkg in _FRAMEWORK_PACKAGES
    )


def capture_source_module(fn: Callable | None) -> str | None:
    """Return the user-app module name for ``fn``, or ``None`` if not user code.

    Reads ``fn.__module__`` directly — Python sets this on every function
    definition, and it survives re-exports, decorators that ``functools.wraps``
    correctly, and aliasing. Returns ``None`` for ``__main__``, missing
    modules, and framework modules.

    Args:
        fn: The user callable whose definition module is wanted.

    Returns:
        The dotted module name to mirror under ``.web/app_components/``, or
        ``None`` to fall back to the per-name un-mirrored output path.
    """
    if fn is None:
        return None
    module_name = getattr(fn, "__module__", None)
    if not module_name or module_name == "__main__":
        return None
    if _is_framework_module(module_name):
        return None
    return module_name


def resolve_user_module_from_frame(skip: int = 0) -> str | None:
    """Walk the live frame stack and return the first user-app module name.

    Used only as a fallback for ``app.add_page(component)`` when the caller
    passed a pre-built ``Component`` instance instead of a callable, so there
    is no ``__module__`` to read directly.

    Args:
        skip: Number of frames above the immediate caller to skip before
            starting the search. Pass ``1`` to ignore the function that is
            calling this helper.

    Returns:
        The first frame's module name that is not a framework module, or
        ``None`` if no suitable frame exists (e.g. running inside a REPL).
    """
    frame = inspect.currentframe()
    if frame is None:
        return None
    frame = frame.f_back
    for _ in range(skip):
        if frame is None:
            return None
        frame = frame.f_back
    while frame is not None:
        module_name = frame.f_globals.get("__name__")
        if (
            module_name
            and module_name != "__main__"
            and not _is_framework_module(module_name)
        ):
            return module_name
        frame = frame.f_back
    return None


# Reserved device names on Windows. A file named like one of these (in any
# case, with or without an extension) can't be created normally, so modules
# with such a segment fall back to the un-mirrored output path.
_WINDOWS_RESERVED_NAMES = frozenset({
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
})


def _segment_is_safe(segment: str) -> bool:
    """Whether ``segment`` is a path-safe Python identifier-like fragment.

    Args:
        segment: A single dotted-module segment.

    Returns:
        True if the segment can be used as a directory or filename without
        introducing path traversal or platform-specific quirks.
    """
    if not segment or segment in {".", ".."}:
        return False
    if any(ch in segment for ch in ("/", "\\", ":", "\0")):
        return False
    # Windows silently strips trailing dots/spaces and reserves device names,
    # either of which breaks the module<->file path correspondence there.
    if segment != segment.rstrip(". "):
        return False
    return segment.casefold() not in _WINDOWS_RESERVED_NAMES


def module_to_mirrored_segments(module_name: str | None) -> tuple[str, ...] | None:
    """Translate a dotted module name to a tuple of mirrored path segments.

    For a *package* (a module whose import resolves to ``__init__.py``), an
    extra ``"index"`` segment is appended so the file lives at
    ``<pkg>/index.jsx`` and submodule files can coexist alongside it as
    siblings under ``<pkg>/``.

    Args:
        module_name: The dotted Python module name. ``None`` short-circuits.

    Returns:
        A tuple of safe path segments to join under ``.web/app_components/``, or
        ``None`` if the module name is missing, contains unsafe segments, or
        cannot be resolved as a package vs. module.
    """
    if not module_name:
        return None
    segments = module_name.split(".")
    if not all(_segment_is_safe(seg) for seg in segments):
        return None
    # Prefer the live module's __file__ over a fresh find_spec lookup. A user
    # can switch a module to a package (or back) between hot-reload compiles,
    # and importlib re-binds __file__ when that happens — a cached find_spec
    # result wouldn't.
    origin: str | None = None
    module = sys.modules.get(module_name)
    if module is not None:
        origin = getattr(module, "__file__", None)
    if origin is None:
        try:
            spec = importlib.util.find_spec(module_name)
        except (ImportError, ValueError):
            spec = None
        if spec is not None:
            origin = spec.origin
    if origin and origin.endswith("__init__.py"):
        return (*segments, "index")
    return tuple(segments)


def library_specifier_for(source_module: str | None) -> str | None:
    """Return the ``$/...`` import specifier mirroring ``source_module``, or None.

    Args:
        source_module: The dotted module name a memo was defined in.

    Returns:
        The ``$/<segments>`` specifier, or ``None`` if no source module was
        captured or it can't be safely mirrored.
    """
    if source_module is None:
        return None
    segments = module_to_mirrored_segments(source_module)
    if segments is None:
        return None
    return mirrored_library_specifier(segments)


def mirrored_jsx_path(web_dir: Path, segments: tuple[str, ...]) -> Path:
    """Build the absolute ``.jsx`` path under ``web_dir`` for ``segments``.

    Mirrored memos live under the reserved ``app_components/`` subdirectory so a
    user module path can never collide with framework output (e.g. a memo in
    module ``app.root`` would otherwise overwrite ``.web/app/root.jsx``).

    Args:
        web_dir: The project's ``.web`` directory.
        segments: Mirrored path segments from
            :func:`module_to_mirrored_segments`.

    Returns:
        The absolute path the compiler should write the memo module to.
    """
    return web_dir.joinpath(Dirs.APP_COMPONENTS, *segments).with_suffix(".jsx")


def mirrored_library_specifier(segments: tuple[str, ...]) -> str:
    """Build the ``$/...`` import specifier for mirrored ``segments``.

    The specifier has no extension; Vite resolves the ``.jsx`` automatically. It
    mirrors :func:`mirrored_jsx_path`, including the reserved ``app_components/``
    subdirectory.

    Args:
        segments: Mirrored path segments from
            :func:`module_to_mirrored_segments`.

    Returns:
        A ``$/`` prefixed module specifier suitable for use as a
        ``Component.library`` value.
    """
    return "$/" + "/".join((Dirs.APP_COMPONENTS, *segments))


def unmirrored_library_specifier(name: str) -> str:
    """Build the ``$/...`` import specifier for an un-mirrorable memo.

    Memos that can't be mirrored to a user module (framework components,
    ``__main__``, unsafe names) get one file per memo under the reserved
    ``app_components/_internal/`` subdirectory.

    Args:
        name: The memo's export name.

    Returns:
        A ``$/`` prefixed module specifier suitable for use as a
        ``Component.library`` value.
    """
    return f"$/{Dirs.APP_COMPONENTS_INTERNAL}/{name}"


def library_for(source_module: str | None, name: str) -> str:
    """Return the library specifier a memo should import from.

    Mirrors ``source_module`` when it can be safely mirrored, otherwise falls
    back to the per-name ``app_components/_internal/<name>`` path.

    Args:
        source_module: The dotted module name a memo was defined in.
        name: The memo's export name, used for the un-mirrored fallback.

    Returns:
        A ``$/`` prefixed module specifier for the memo's compiled output.
    """
    return library_specifier_for(source_module) or unmirrored_library_specifier(name)
