"""A text component."""
from __future__ import annotations

from nextpy.components.libs.chakra import ChakraComponent
from nextpy.core.vars import Var


class Text(ChakraComponent):
    """Render a paragraph of text."""

    tag = "Text"

    # Override the tag. The default tag is `<p>`.
    as_: Var[str]
