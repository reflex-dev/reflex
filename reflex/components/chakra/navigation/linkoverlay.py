"""Link overlay components."""
from typing import Optional

from reflex.components.chakra import ChakraComponent
from reflex.vars import Var


class LinkOverlay(ChakraComponent):
    """Wraps child component in a link."""

    tag = "LinkOverlay"

    # If true, the link will open in new tab
    is_external: Optional[Var[bool]] = None

    # Href of the link overlay.
    href: Optional[Var[str]] = None


class LinkBox(ChakraComponent):
    """The LinkBox lifts any nested links to the top using z-index to ensure proper keyboard navigation between links."""

    tag = "LinkBox"
