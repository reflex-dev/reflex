# pyright: reportWildcardImportFromLibrary=false
"""Re-export from reflex_base."""

from typing import Any

from reflex_base.components.dynamic import *  # pragma: no cover


def __getattr__(name: str) -> Any:
    """Delegate to `reflex_base.components.dynamic` for names the star import misses.

    Args:
        name: The name of the attribute to look up.

    Returns:
        The attribute from the re-exported module.

    Raises:
        AttributeError: If the re-exported module has no such attribute.
    """
    from reflex_base.components import dynamic

    try:
        return getattr(dynamic, name)
    except AttributeError:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg) from None
