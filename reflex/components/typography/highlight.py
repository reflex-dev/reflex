"""A highlight component."""

from typing import List

from reflex.components.libs.chakra import ChakraComponent
from reflex.components.tags import Tag
from reflex.vars import Dict, Var


class Highlight(ChakraComponent):
    """Highlights a specific part of a string."""

    tag = "Highlight"

    # A query for the text to highlight. Can be a string or a list of strings.
    query: Var[List[str]]

    # The style of the content.
    # Note: styles and style are different prop.
    styles: Var[Dict] = {"px": "2", "py": "1", "rounded": "full", "bg": "teal.100"}  # type: ignore

    def _render(self) -> Tag:
        return super()._render().add_props(styles=self.style)
