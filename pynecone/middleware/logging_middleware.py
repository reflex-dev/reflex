"""Logging middleware."""
from __future__ import annotations

from typing import TYPE_CHECKING

from pynecone.event import Event
from pynecone.middleware.middleware import Middleware
from pynecone.state import Delta, State

if TYPE_CHECKING:
    from pynecone.app import App


class LoggingMiddleware(Middleware):
    """Middleware to log requests and responses."""

    def preprocess(self, app: App, state: State, event: Event):
        """Preprocess the event.

        Args:
            app: The app to apply the middleware to.
            state: The client state.
            event: The event to preprocess.
        """
        print(f"Event {event}")

    def postprocess(self, app: App, state: State, event: Event, delta: Delta):
        """Postprocess the event.

        Args:
            app: The app to apply the middleware to.
            state: The client state.
            event: The event to postprocess.
            delta: The delta to postprocess.
        """
        print(f"Delta {delta}")
