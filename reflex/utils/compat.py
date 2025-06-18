"""Compatibility hacks and helpers."""

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


def sqlmodel_field_has_primary_key(field: Any) -> bool:
    """Determines if a field is a primary.

    Args:
        field: a rx.model field

    Returns:
        If field is a primary key (Bool)
    """
    if getattr(field.field_info, "primary_key", None) is True:
        return True
    if getattr(field.field_info, "sa_column", None) is None:
        return False
    return bool(getattr(field.field_info.sa_column, "primary_key", None))
