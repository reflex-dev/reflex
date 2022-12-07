"""A text component."""
from __future__ import annotations

from pynecone.components.libs.chakra import ChakraComponent
from pynecone.var import Var


class Text(ChakraComponent):
    """Render a paragraph of text."""

    tag = "Text"

    # The text to display.
    text: Var[str]

    # The CSS `text-align` property
    text_align: Var[str]

    # The CSS `text-transform` property
    casing: Var[str]

    # The CSS `text-decoration` property
    decoration: Var[str]

    # Override the tag.
    as_: Var[str]
