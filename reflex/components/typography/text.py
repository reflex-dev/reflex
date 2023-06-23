"""A text component."""
from __future__ import annotations

from reflex.components.libs.chakra import ChakraComponent
from reflex.vars import Var


class Text(ChakraComponent):
    """Render a paragraph of text."""

    tag = "Text"

    # Override the tag. The default tag is `<p>`.
    as_: Var[str]
