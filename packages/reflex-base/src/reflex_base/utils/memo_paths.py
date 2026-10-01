"""Mirror user-app Python module paths into the compiler's ``.web`` output.

The compiler uses these helpers to write each memo's compiled JSX to a path
under ``.web/app_components/`` that mirrors its Python source module, instead of
bundling everything into one file. This module owns the small set of helpers
that:

- Read ``fn.__module__``, rejecting only synthetic modules (``__main__``,
  missing). Framework modules mirror to their real package name like any other.
- Walk the live frame stack as a fallback for entry points that don't take a
  user-supplied callable (notably ``app.add_page(component)`` with a Component
  instance), skipping framework frames to reach the real user module.
- Translate a dotted Python module name into mirrored JSX path segments and
  the corresponding ``$/...`` library specifier consumed by the import system.
"""

from __future__ import annotations

import hashlib
import importlib.util
import inspect
import sys
from collections.abc import Callable
from pathlib import Path

from reflex_base.constants.base import Dirs

# Framework packages, matched by exact name or dotted-prefix, used only to steer
# the frame-walk fallback (:func:`resolve_user_module_from_frame`) past framework
# frames to the real user module. Memos defined in these packages still mirror to
# their real package name like any other module.
#
# Matched by exact name plus a dot boundary rather than a bare prefix so a
# developer's own package can't be mistaken for the framework — notably the
# ``reflex_components_*`` family is *not* listed: that's the convention community
# component libraries follow, none of them wrap ``add_page`` (the only thing the
# frame walk skips), and if one did we'd want its memos mirrored to its real
# package name anyway.
_FRAMEWORK_PACKAGES = (
    "reflex",
    "reflex_base",
    "reflex_site_shared",
    "reflex_hosting_cli",
    "reflex_docgen",
)


def _is_framework_module(module_name: str) -> bool:
    """Whether ``module_name`` belongs to the framework itself.

    Used only by :func:`resolve_user_module_from_frame` to skip framework
    frames; framework modules are otherwise mirrored like any user module.

    Args:
        module_name: The dotted module name.

    Returns:
        True if the module is part of the framework.
    """
    return any(
        module_name == pkg or module_name.startswith(pkg + ".")
        for pkg in _FRAMEWORK_PACKAGES
    )


def capture_source_module(fn: Callable | None) -> str | None:
    """Return the user-app module name for ``fn``, or ``None`` if not user code.

    Reads ``fn.__module__`` directly — Python sets this on every function
    definition, and it survives re-exports, decorators that ``functools.wraps``
    correctly, and aliasing. Returns ``None`` only for ``__main__`` and missing
    modules, which have no stable path to mirror; framework modules mirror to
    their real package name like any other.

    Args:
        fn: The callable whose definition module is wanted.

    Returns:
        The dotted module name to mirror under ``.web/app_components/``, or
        ``None`` to fall back to the per-name un-mirrored output path.
    """
    if fn is None:
        return None
    module_name = getattr(fn, "__module__", None)
    if not module_name or module_name == "__main__":
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

    Memos that can't be mirrored to a source module (``__main__``, unsafe
    names) get one file per memo under ``utils/components/`` — the legacy
    per-name layout.

    Args:
        name: The memo's export name.

    Returns:
        A ``$/`` prefixed module specifier suitable for use as a
        ``Component.library`` value.
    """
    return f"$/{Dirs.COMPONENTS_PATH}/{name}"


def library_for(source_module: str | None, name: str) -> str:
    """Return the library specifier a memo should import from.

    Mirrors ``source_module`` when it can be safely mirrored, otherwise falls
    back to the per-name ``utils/components/<name>`` path.

    Args:
        source_module: The dotted module name a memo was defined in.
        name: The memo's export name, used for the un-mirrored fallback.

    Returns:
        A ``$/`` prefixed module specifier for the memo's compiled output.
    """
    if source_module is not None:
        segments = module_to_mirrored_segments(source_module)
        if segments is not None:
            return mirrored_library_specifier(segments)
    return unmirrored_library_specifier(name)


def mirrored_symbol(name: str, source_module: str) -> str:
    """Return the unique JS symbol a mirrored memo exports and imports under.

    Two memos with the same ``name`` in different modules must compile to
    different JS symbols, or a page importing both hits a tag collision. The
    output file already mirrors ``source_module``; this gives the symbol the
    same per-module uniqueness by appending a short hash of the full dotted
    module name. The hash is taken over the dotted name rather than the mirrored
    segments so it stays injective: ``a.b`` and ``a_b`` collapse to the same
    segments but hash differently.

    Args:
        name: The memo's clean export name (e.g. ``MyWidget``).
        source_module: The dotted Python module the memo was defined in.

    Returns:
        A valid JS identifier unique to ``(name, source_module)``.
    """
    suffix = hashlib.sha1(source_module.encode()).hexdigest()[:8]
    return f"{name}_{suffix}"


def library_and_symbol(source_module: str | None, name: str) -> tuple[str, str]:
    """Return the library specifier and JS symbol a memo compiles to.

    Mirrors :func:`library_for` but also returns the symbol, computing the
    mirrored segments once so the library and the symbol can never disagree
    about whether the module is mirrorable.

    Args:
        source_module: The dotted module name a memo was defined in.
        name: The memo's export name.

    Returns:
        A ``(library, symbol)`` pair. For an un-mirrorable memo the symbol is
        ``name`` unchanged and the library is the per-name fallback path.
    """
    if source_module is not None:
        segments = module_to_mirrored_segments(source_module)
        if segments is not None:
            return mirrored_library_specifier(segments), mirrored_symbol(
                name, source_module
            )
    return unmirrored_library_specifier(name), name
