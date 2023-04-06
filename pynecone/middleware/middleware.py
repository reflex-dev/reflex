"""Base Pynecone middleware."""
from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING, List, Optional, Union

from pynecone.base import Base
from pynecone.event import Event
from pynecone.state import Delta, State, StateUpdate

if TYPE_CHECKING:
    from pynecone.app import App


class Middleware(Base, ABC):
    """Middleware to preprocess and postprocess requests."""

    async def preprocess(
        self, app: App, state: State, event: Event
    ) -> Optional[Union[StateUpdate, List[StateUpdate]]]:
        """Preprocess the event.

        Args:
            app: The app.
            state: The client state.
            event: The event to preprocess.

        Returns:
            An optional state to return.
        """
        return None

    async def postprocess(
        self, app: App, state: State, event: Event, delta
    ) -> Optional[Delta]:
        """Postprocess the event.

        Args:
            app: The app.
            state: The client state.
            event: The event to postprocess.
            delta: The delta to postprocess.

        Returns:
            An optional state to return.
        """
        return None
