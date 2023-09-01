"""Banner components."""
from __future__ import annotations

from typing import Optional

from reflex.components.component import Component
from reflex.components.layout import Box, Cond
from reflex.components.overlay.modal import Modal
from reflex.components.typography import Text
from reflex.vars import Var

connection_error: Var = Var.create_safe(
    value="(connectError !== null) ? connectError.message : ''",
    is_local=False,
    is_string=False,
)
has_connection_error: Var = Var.create_safe(
    value="connectError !== null",
    is_string=False,
)
has_connection_error.type_ = bool


def default_connection_error() -> list[str | Var]:
    """Get the default connection error message.

    Returns:
        The default connection error message.
    """
    from reflex.config import get_config

    return [
        "Cannot connect to server: ",
        connection_error,
        ". Check if server is reachable at ",
        get_config().api_url or "<API_URL not set>",
    ]


class ConnectionBanner(Component):
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
                    *default_connection_error(),
                    bg="red",
                    color="white",
                ),
                textAlign="center",
            )

        return Cond.create(has_connection_error, comp)


class ConnectionModal(Component):
    """A connection status modal window."""

    @classmethod
    def create(cls, comp: Optional[Component] = None) -> Component:
        """Create a connection banner component.

        Args:
            comp: The component to render when there's a server connection error.

        Returns:
            The connection banner component.
        """
        if not comp:
            comp = Text.create(*default_connection_error())
        return Cond.create(
            has_connection_error,
            Modal.create(
                header="Connection Error",
                body=comp,
                is_open=has_connection_error,
            ),
        )
