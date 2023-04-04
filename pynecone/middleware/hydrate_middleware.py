"""Middleware to hydrate the state."""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Union

from pynecone import constants
from pynecone.event import Event, EventHandler, get_hydrate_event
from pynecone.middleware.middleware import Middleware
from pynecone.state import Delta, State, StateUpdate
from pynecone.utils import format

if TYPE_CHECKING:
    from pynecone.app import App


class HydrateMiddleware(Middleware):
    """Middleware to handle initial app hydration."""

    async def preprocess(
        self, app: App, state: State, event: Event
    ) -> Union[Optional[Delta], List[StateUpdate]]:
        """Preprocess the event.

        Args:
            app: The app to apply the middleware to.
            state: The client state.
            event: The event to preprocess.

        Returns:
            An optional delta or list of state updates to return.
        """
        if event.name == get_hydrate_event(state):
            route = event.router_data.get(constants.RouteVar.PATH, "")
            if route == "/":
                load_event = app.load_events.get(constants.INDEX_ROUTE)
            elif route:
                load_event = app.load_events.get(route.lstrip("/"))
            else:
                load_event = None

            if load_event:
                if not isinstance(load_event, List):
                    load_event = [load_event]
                updates = []
                for single_event in load_event:
                    updates.append(
                        await self.execute_load_event(
                            state, single_event, event.token, event.payload
                        )
                    )
                return updates
            return format.format_state({state.get_name(): state.dict()})

    async def execute_load_event(
        self, state: State, load_event: EventHandler, token: str, payload: Dict
    ) -> StateUpdate:
        """Execute single load event.

        Args:
            state: The client state.
            load_event: A single load event to execute.
            token: client token
            payload: the event payload

        Returns:
            A state Update.

        Raises:
            ValueError: If the state value is None.
        """
        substate_path = format.format_event_handler(load_event).split(".")
        ex_state = state.get_substate(substate_path[:-1])
        if ex_state:
            return await state.process_event(
                handler=load_event, state=ex_state, payload=payload, token=token
            )
        else:
            raise ValueError(
                "The value of state cannot be None when processing an on-load event."
            )
