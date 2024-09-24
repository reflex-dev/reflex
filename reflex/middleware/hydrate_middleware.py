"""Middleware to hydrate the state."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Optional

from reflex import constants
from reflex.event import Event, get_hydrate_event
from reflex.middleware.middleware import Middleware
from reflex.state import BaseState, StateUpdate
from reflex.utils import format

if TYPE_CHECKING:
    from reflex.app import App


@dataclasses.dataclass(init=True)
class HydrateMiddleware(Middleware):
    """Middleware to handle initial app hydration."""

    async def preprocess(
        self, app: App, state: BaseState, event: Event
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

        # Clear client storage, to respect clearing cookies
        state._reset_client_storage()

        # Mark state as not hydrated (until on_loads are complete)
        setattr(state, constants.CompileVars.IS_HYDRATED, False)

        # Get the initial state.
        delta = format.format_state(state.dict())
        # since a full dict was captured, clean any dirtiness
        state._clean()

        # Return the state update.
        return StateUpdate(delta=delta, events=[])
