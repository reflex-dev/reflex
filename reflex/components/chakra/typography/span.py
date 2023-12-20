"""A span component."""
from __future__ import annotations

from reflex.components.libs.chakra import ChakraComponent
from reflex.vars import Var


class Span(ChakraComponent):
    """Render an inline span of text."""

    tag = "Text"

    # Override the tag. The default tag is `<span>`.
    as_: Var[str] = "span"  # type: ignore
