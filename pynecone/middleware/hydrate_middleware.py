"""Middleware to hydrate the state."""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from pynecone import constants, utils
from pynecone.event import Event, EventHandler
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
            route = event.router_data.get(constants.RouteVar.PATH, "")
            if route == "/":
                load_event = app.load_events.get(constants.INDEX_ROUTE)
            elif route:
                load_event = app.load_events.get(route.lstrip("/"))
            else:
                load_event = None

            if load_event:
                if isinstance(load_event, list):
                    for single_event in load_event:
                        self.execute_load_event(state, single_event)
                else:
                    self.execute_load_event(state, load_event)
            return utils.format_state({state.get_name(): state.dict()})

    def execute_load_event(self, state: State, load_event: EventHandler) -> None:
        """Execute single load event.

        Args:
            state: The client state.
            load_event: A single load event to execute.
        """
        substate_path = utils.format_event_handler(load_event).split(".")
        ex_state = state.get_substate(substate_path[:-1])
        load_event.fn(ex_state)
