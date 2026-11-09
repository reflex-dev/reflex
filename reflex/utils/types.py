# pyright: reportWildcardImportFromLibrary=false
"""Re-export from reflex_base."""

from typing import TYPE_CHECKING

import reflex_base.utils.types as _types

if TYPE_CHECKING:
    from reflex_base.utils.types import *
    from reflex_base.utils.types import PROPERTY_CLASSES as PROPERTY_CLASSES
else:
    __all__ = list(_types.__all__)
    globals().update({
        name: _types.__dict__[name] for name in __all__ if name != "PROPERTY_CLASSES"
    })


def __getattr__(name: str) -> object:
    """Forward lazy compatibility attributes to reflex_base.

    Args:
        name: The module attribute being requested.

    Returns:
        The corresponding reflex_base type utility.

    Raises:
        AttributeError: If reflex_base does not define the requested attribute.
    """
    return getattr(_types, name)


def __dir__() -> list[str]:
    """List local and reflex_base type utility attributes.

    Returns:
        The combined module attribute names.
    """
    return sorted(set(globals()) | set(dir(_types)))
