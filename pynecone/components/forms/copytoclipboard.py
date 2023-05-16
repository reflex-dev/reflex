"""A copy to clipboard component."""

from typing import Set

from pynecone.components import Component
from pynecone.vars import Var


class CopyToClipboard(Component):
    """Component to copy text to clipboard."""

    library = "react-copy-to-clipboard"

    tag = "CopyToClipboard"

    # The text to copy when clicked.
    text: Var[str]

    def get_controlled_triggers(self) -> Set[str]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            The controlled event triggers.
        """
        return {"on_copy"}
