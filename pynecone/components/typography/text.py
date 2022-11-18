"""A text component."""
from __future__ import annotations

from pynecone.components.libs.chakra import ChakraComponent
from pynecone.components.tags import Tag
from pynecone.var import Var


class Text(ChakraComponent):
    """Text component is the used to render text and paragraphs within an interface. It renders a p tag by default."""

    tag = "Text"

    # The text to display.
    text: Var[str]

    # The CSS `text-align` property
    text_align: Var[str]

    # The CSS `text-transform` property
    casing: Var[str]

    # The CSS `text-decoration` property
    decoration: Var[str]

    # Override the text element. Tpyes are b, strong, i, em, mark, small, del, ins, sub, and sup.
    as_: Var[str]
