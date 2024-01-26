"""A span component."""
from __future__ import annotations

from reflex.components.chakra import ChakraComponent
from reflex.vars import Var


class Span(ChakraComponent):
    """Render an inline span of text."""

    library = "@chakra-ui/layout@2.3.1"

    tag = "Text"

    # Override the tag. The default tag is `<span>`.
    as_: Var[str] = "span"  # type: ignore
