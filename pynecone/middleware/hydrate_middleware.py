"""Middleware to hydrate the state."""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from pynecone import constants
from pynecone.event import Event, fix_events, get_hydrate_event
from pynecone.middleware.middleware import Middleware
from pynecone.state import State, StateUpdate
from pynecone.utils import format

if TYPE_CHECKING:
    from pynecone.app import App


IS_HYDRATED = "is_hydrated"


State.add_var(IS_HYDRATED, type_=bool, default_value=False)


class HydrateMiddleware(Middleware):
    """Middleware to handle initial app hydration."""

    async def preprocess(
        self, app: App, state: State, event: Event
    ) -> Optional[StateUpdate]:
        """Preprocess the event.

        Args:
            app: The app to apply the middleware to.
            state: The client state.
            event: The event to preprocess.

        Returns:
            An optional delta or list of state updates to return.
        """
        if event.name != get_hydrate_event(state):
            return None
        route = event.router_data.get(constants.RouteVar.PATH, "")
        return StateUpdate(
            delta=format.format_state({state.get_name(): state.dict()}),
            events=fix_events(app.get_load_events(route), event.token),  # type: ignore
        )
