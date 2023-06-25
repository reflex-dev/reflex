"""Middleware to hydrate the state."""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from reflex import constants
from reflex.event import Event, fix_events, get_hydrate_event
from reflex.middleware.middleware import Middleware
from reflex.state import State, StateUpdate
from reflex.utils import format

if TYPE_CHECKING:
    from reflex.app import App


State.add_var(constants.IS_HYDRATED, type_=bool, default_value=False)


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
        # If this is not the hydrate event, return None
        if event.name != get_hydrate_event(state):
            return None

        # Get the initial state.
        setattr(state, constants.IS_HYDRATED, False)
        delta = format.format_state({state.get_name(): state.dict()})
        # since a full dict was captured, clean any dirtiness
        state.clean()

        # Get the route for on_load events.
        route = event.router_data.get(constants.RouteVar.PATH, "")

        # Add the on_load events and set is_hydrated to True.
        events = [*app.get_load_events(route), type(state).set_is_hydrated(True)]  # type: ignore
        events = fix_events(events, event.token)

        # Return the state update.
        return StateUpdate(delta=delta, events=events)
