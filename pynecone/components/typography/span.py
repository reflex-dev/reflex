"""A span component."""
from __future__ import annotations

from pynecone.components.libs.chakra import ChakraComponent
from pynecone.var import Var


class Span(ChakraComponent):
    """Render an inline span of text."""

    tag = "Text"

    # Override the tag. The default tag is `<span>`.
    as_: Var[str] = "span"  # type: ignore
