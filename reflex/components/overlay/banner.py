"""Banner components."""
from __future__ import annotations

from typing import Optional

from reflex.components.base.bare import Bare
from reflex.components.component import Component
from reflex.components.layout import Box, cond
from reflex.components.overlay.modal import Modal
from reflex.components.typography import Text
from reflex.constants import Hooks, Imports
from reflex.utils import imports
from reflex.vars import Var, VarData

connect_error_var_data: VarData = VarData(  # type: ignore
    imports=Imports.EVENTS,
    hooks={Hooks.EVENTS},
)

connection_error: Var = Var.create_safe(
    value="(connectError !== null) ? connectError.message : ''",
    _var_is_local=False,
    _var_is_string=False,
)._replace(merge_var_data=connect_error_var_data)
has_connection_error: Var = Var.create_safe(
    value="connectError !== null",
    _var_is_string=False,
)._replace(_var_type=bool, merge_var_data=connect_error_var_data)


class WebsocketTargetURL(Bare):
    """A component that renders the websocket target URL."""

    def _get_imports(self) -> imports.ImportDict:
        return {
            "/utils/state.js": [imports.ImportVar(tag="getEventURL")],
        }

    @classmethod
    def create(cls) -> Component:
        """Create a websocket target URL component.

        Returns:
            The websocket target URL component.
        """
        return super().create(contents="{getEventURL().href}")


def default_connection_error() -> list[str | Var | Component]:
    """Get the default connection error message.

    Returns:
        The default connection error message.
    """
    return [
        "Cannot connect to server: ",
        connection_error,
        ". Check if server is reachable at ",
        WebsocketTargetURL.create(),
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

        return cond(has_connection_error, comp)


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
        return cond(
            has_connection_error,
            Modal.create(
                header="Connection Error",
                body=comp,
                is_open=has_connection_error,
            ),
        )
