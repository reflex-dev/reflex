"""Middleware to hydrate the state."""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from pynecone import constants, utils
from pynecone.event import Event
from pynecone.middleware.middleware import Middleware
from pynecone.state import Delta, State

if TYPE_CHECKING:
    from pynecone.app import App


class HydrateMiddleware(Middleware):
    """Middleware to handle initial app hydration."""

    def preprocess(self, app: App, state: State, event: Event) -> Optional[Delta]:
        """Preprocess the event.

        Args:
            app: The app to apply the middleware to.
            state: The client state.
            event: The event to preprocess.

        Returns:
            An optional state to return.
        """
        if event.name == utils.get_hydrate_event(state):
            return utils.format_state({state.get_name(): state.dict()})
