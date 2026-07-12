"""Walk the Python call stack and record where a component was created."""

from __future__ import annotations

import dataclasses
import hashlib
import sys
from pathlib import Path

from reflex_base.utils import frames

from . import state


@dataclasses.dataclass(frozen=True, slots=True)
class SourceInfo:
    """A user-code frame that constructed a component."""

    file: str
    line: int
    column: int
    component: str


_REGISTRY: dict[int, SourceInfo] = {}
_BY_INFO: dict[SourceInfo, int] = {}
_FRAMEWORK_ROOTS: tuple[Path, ...] = ()
_RESOLVED_PATH_CACHE: dict[str, str] = {}


def _get_framework_roots() -> tuple[Path, ...]:
    return _FRAMEWORK_ROOTS


_is_framework_frame = frames.make_framework_frame_predicate(_get_framework_roots)


def _ensure_framework_roots() -> None:
    global _FRAMEWORK_ROOTS
    if not _FRAMEWORK_ROOTS:
        _FRAMEWORK_ROOTS = frames.discover_framework_roots()


def _resolve_filename(filename: str) -> str:
    cached = _RESOLVED_PATH_CACHE.get(filename)
    if cached is not None:
        return cached
    try:
        resolved = str(Path(filename).resolve())
    except OSError:
        resolved = filename
    _RESOLVED_PATH_CACHE[filename] = resolved
    return resolved


def _stable_id(info: SourceInfo) -> int:
    """Hash a source location to a 32-bit id.

    The same ``(file, line, column, component)`` always hashes to the same
    id, so a ``multiprocessing.spawn``-ed worker can re-capture at request
    time and produce ids that match ``source-map.json`` written by the
    parent's compile pass.

    Args:
        info: The source location to hash.

    Returns:
        A 32-bit unsigned integer derived from the source location.
    """
    key = (f"{info.file}\x00{info.line}\x00{info.column}\x00{info.component}").encode()
    return int.from_bytes(hashlib.blake2b(key, digest_size=4).digest(), "big")


def capture(component_name: str) -> int | None:
    """Walk the call stack and return an inspector id for the user frame.

    Args:
        component_name: ``cls.__name__`` of the component being constructed.

    Returns:
        A deterministic integer id when the inspector is enabled and a
        non-framework frame is found; ``None`` otherwise (e.g. inspector
        disabled, only framework code on the stack).
    """
    if not state.is_enabled():
        return None
    _ensure_framework_roots()
    user_frame = frames.walk_to_first_non_framework_frame(
        sys._getframe(1), _is_framework_frame
    )
    try:
        if user_frame is None:
            return None
        info = SourceInfo(
            file=_resolve_filename(user_frame.f_code.co_filename),
            line=user_frame.f_lineno,
            column=1,
            component=component_name,
        )
        if (existing := _BY_INFO.get(info)) is not None:
            return existing
        cid = _stable_id(info)
        # 32-bit collisions are vanishingly rare, but the cost of getting
        # it wrong is "wrong file opens in editor". Resalt until unique.
        salt = 0
        while (claimed := _REGISTRY.get(cid)) is not None and claimed != info:
            salt += 1
            cid = _stable_id(
                dataclasses.replace(info, column=info.column + salt * 1_000_000)
            )
        _REGISTRY[cid] = info
        _BY_INFO[info] = cid
        return cid
    finally:
        # Break the local frame reference so the captured frame's locals
        # (which can transitively reference this function) become reclaimable.
        del user_frame


def snapshot() -> dict[int, SourceInfo]:
    """Return a copy of the current registry.

    Returns:
        A shallow copy of the inspector id → ``SourceInfo`` mapping.
    """
    return dict(_REGISTRY)


def reset() -> None:
    """Clear the registry. Intended for tests and per-compile resets.

    Framework roots are also cleared so the next ``capture`` rediscovers
    them — covers framework subpackages imported between compile passes.
    """
    global _FRAMEWORK_ROOTS
    _REGISTRY.clear()
    _BY_INFO.clear()
    _FRAMEWORK_ROOTS = ()
    _is_framework_frame.cache_clear()
    _RESOLVED_PATH_CACHE.clear()
