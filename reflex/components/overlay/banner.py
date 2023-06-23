"""Banner components."""
from typing import Optional

from reflex.components.component import Component
from reflex.components.layout import Box, Cond, Fragment
from reflex.components.typography import Text
from reflex.vars import Var


class ConnectionBanner(Cond):
    """A connection banner component."""

    @classmethod
    def create(cls, comp: Optional[Component] = None) -> Component:
        """Create a connection banner component.

        Args:
            comp: The component to render when there's a server connection error.

        Returns:
            The connection banner component.
        """
        if not comp:
            comp = Box.create(
                Text.create(
                    "cannot connect to server. Check if server is reachable",
                    bg="red",
                    color="white",
                ),
                textAlign="center",
            )

        return super().create(Var.create("notConnected"), comp, Fragment.create())  # type: ignore
