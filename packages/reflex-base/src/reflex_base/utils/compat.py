"""Compatibility hacks and helpers."""

import sys
from collections.abc import Mapping
from functools import lru_cache
from typing import Any

if sys.version_info >= (3, 14):
    from annotationlib import (
        Format,
        call_annotate_function,
        get_annotate_from_class_namespace,
        get_annotations,
    )


async def windows_hot_reload_lifespan_hack():
    """[REF-3164] A hack to fix hot reload on Windows.

    Uvicorn has an issue stopping itself on Windows after detecting changes in
    the filesystem.

    This workaround repeatedly prints and flushes null characters to stderr,
    which seems to allow the uvicorn server to exit when the CTRL-C signal is
    sent from the reloader process.

    Don't ask me why this works, I discovered it by accident - masenf.
    """
    import asyncio
    import sys

    try:
        while True:
            sys.stderr.write("\0")
            sys.stderr.flush()
            await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        pass


def annotations_from_namespace(namespace: Mapping[str, Any]) -> dict[str, Any]:
    """Get the annotations from a class namespace.

    Args:
        namespace: The class namespace.

    Returns:
        The (forward-ref) annotations from the class namespace.
    """
    if sys.version_info >= (3, 14) and "__annotations__" not in namespace:
        if annotate := get_annotate_from_class_namespace(namespace):
            return call_annotate_function(annotate, format=Format.FORWARDREF)
    return namespace.get("__annotations__", {})


@lru_cache
def _mro_annotation_names(cls: type) -> frozenset[str]:
    """All annotation names declared across ``cls``'s MRO.

    Never evaluates annotation values, which under PEP 649 lazy evaluation
    (3.14+) may raise NameError. Cached: annotations added later are not seen.

    Args:
        cls: The class to inspect.

    Returns:
        The annotation names declared in the MRO.
    """
    if sys.version_info >= (3, 14):
        return frozenset(
            name
            for klass in cls.__mro__
            for name in get_annotations(klass, format=Format.STRING)
        )
    return frozenset(
        name for klass in cls.__mro__ for name in getattr(klass, "__annotations__", {})
    )


def declares_annotation(cls: type, name: str) -> bool:
    """Whether ``name`` is annotated on any class in ``cls``'s MRO.

    Args:
        cls: The class to inspect.
        name: The attribute name to look for.

    Returns:
        Whether ``name`` is annotated.
    """
    return name in _mro_annotation_names(cls)
