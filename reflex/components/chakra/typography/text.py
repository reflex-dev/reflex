"""A text component."""
from __future__ import annotations

from typing import Optional

from reflex.components.chakra import ChakraComponent
from reflex.vars import Var


class Text(ChakraComponent):
    """Render a paragraph of text."""

    tag: str = "Text"

    # Override the tag. The default tag is `<p>`.
    as_: Optional[Var[str]] = None

    # Truncate text after a specific number of lines. It will render an ellipsis when the text exceeds the width of the viewport or max_width prop.
    no_of_lines: Optional[Var[int]] = None
