"""Middleware to hydrate the state."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Optional

from reflex import constants
from reflex.compiler.utils import save_error
from reflex.event import Event, get_hydrate_event
from reflex.middleware.middleware import Middleware
from reflex.state import BaseState, StateUpdate, _resolve_delta
from reflex.utils import console

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

        try:
            initial_state = state.dict()
        except Exception as e:
            log_path = save_error(e)
            console.error(
                f"Failed to compile initial state with computed vars. Error log saved to {log_path}"
            )
            initial_state = state.dict(call_computed=False)

        # Get the initial state.
        delta = await _resolve_delta(initial_state)

        # since a full dict was captured, clean any dirtiness
        state._clean()

        # Return the state update.
        return StateUpdate(delta=delta, events=[])
