"""Base Reflex middleware."""
from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING, Optional

from reflex.base import Base
from reflex.event import Event
from reflex.state import BaseState, StateUpdate

if TYPE_CHECKING:
    from reflex.app import App


class Middleware(Base, ABC):
    """Middleware to preprocess and postprocess requests."""

    async def preprocess(
        self, app: App, state: BaseState, event: Event
    ) -> Optional[StateUpdate]:
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
