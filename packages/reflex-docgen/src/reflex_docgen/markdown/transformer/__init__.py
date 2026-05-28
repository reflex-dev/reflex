"""Document transformers for converting parsed markdown into other formats."""

from __future__ import annotations

from typing import TYPE_CHECKING

from reflex_docgen.markdown.transformer._base import (
    DocumentTransformer as DocumentTransformer,
)
from reflex_docgen.markdown.transformer._markdown import (
    MarkdownTransformer as MarkdownTransformer,
)

if TYPE_CHECKING:
    from reflex_docgen.markdown.transformer._reflex import (
        ReflexComponentTransformer as ReflexComponentTransformer,
    )

__all__ = [
    "DocumentTransformer",
    "MarkdownTransformer",
    "ReflexComponentTransformer",
]


def __getattr__(name: str) -> object:
    """Lazily import the reflex-dependent transformer on first access.

    Keeps ``import reflex_docgen.markdown`` (and the markdown-string
    transformer) free of a hard ``reflex`` import until the component
    transformer is actually used.

    Args:
        name: The attribute being accessed.

    Returns:
        The resolved attribute.

    Raises:
        AttributeError: If the attribute does not exist.
    """
    if name == "ReflexComponentTransformer":
        from reflex_docgen.markdown.transformer._reflex import (
            ReflexComponentTransformer,
        )

        return ReflexComponentTransformer
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
