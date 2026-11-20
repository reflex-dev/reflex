# pyright: reportWildcardImportFromLibrary=false
"""Re-export from reflex_base."""

from typing import Any

from reflex_base.utils import exceptions as _base_exceptions
from reflex_base.utils.exceptions import *  # pragma: no cover


def __getattr__(name: str) -> Any:
    """Forward the deprecated exception names reflex_base resolves on use.

    Args:
        name: The module attribute being requested.

    Returns:
        The attribute of reflex_base.utils.exceptions.
    """
    return getattr(_base_exceptions, name)
