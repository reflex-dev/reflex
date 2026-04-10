"""Compatibility hacks and helpers."""

import sys
from collections.abc import Mapping
from typing import Any


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
        from annotationlib import (
            Format,
            call_annotate_function,
            get_annotate_from_class_namespace,
        )

        if annotate := get_annotate_from_class_namespace(namespace):
            return call_annotate_function(annotate, format=Format.FORWARDREF)
    return namespace.get("__annotations__", {})
