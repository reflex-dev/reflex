"""Base Reflex middleware."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

from reflex_base.event import Event

from reflex.state import BaseState, StateUpdate

if TYPE_CHECKING:
    from reflex.app import App


class Middleware(ABC):
    """Middleware to preprocess and postprocess requests."""

    # Whether preprocess also runs for stateless event handlers. The token's
    # state is locked while it runs, so a stateless handler waits for the
    # lock when any installed middleware keeps this on.
    preprocess_stateless: ClassVar[bool] = True

    @abstractmethod
    async def preprocess(
        self, app: App, state: BaseState, event: Event
    ) -> StateUpdate | None:
        """Preprocess the event.

        Args:
            app: The app.
            state: The client state.
            event: The event to preprocess.

        Returns:
            An optional state update to return.
        """
        return None

    async def postprocess(
        self, app: App, state: BaseState, event: Event, update: StateUpdate
    ) -> StateUpdate:
        """Postprocess the event.

        Args:
            app: The app.
            state: The client state.
            event: The event to postprocess.
            update: The current state update.

        Returns:
            An optional state to return.
        """
        return update
