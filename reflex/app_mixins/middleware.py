"""Middleware Mixin that allow to add middleware to the app."""

from __future__ import annotations

import asyncio
import dataclasses
from typing import List

from reflex.event import Event
from reflex.middleware import HydrateMiddleware, Middleware
from reflex.state import BaseState, StateUpdate

from .mixin import AppMixin


@dataclasses.dataclass
class MiddlewareMixin(AppMixin):
    """Middleware Mixin that allow to add middleware to the app."""

    # Middleware to add to the app. Users should use `add_middleware`. PRIVATE.
    middleware: List[Middleware] = dataclasses.field(default_factory=list)

    def _init_mixin(self):
        self.middleware.append(HydrateMiddleware())

    def add_middleware(self, middleware: Middleware, index: int | None = None):
        """Add middleware to the app.

        Args:
            middleware: The middleware to add.
            index: The index to add the middleware at.
        """
        if index is None:
            self.middleware.append(middleware)
        else:
            self.middleware.insert(index, middleware)

    async def _preprocess(self, state: BaseState, event: Event) -> StateUpdate | None:
        """Preprocess the event.

        This is where middleware can modify the event before it is processed.
        Each middleware is called in the order it was added to the app.

        If a middleware returns an update, the event is not processed and the
        update is returned.

        Args:
            state: The state to preprocess.
            event: The event to preprocess.

        Returns:
            An optional state to return.
        """
        for middleware in self.middleware:
            if asyncio.iscoroutinefunction(middleware.preprocess):
                out = await middleware.preprocess(app=self, state=state, event=event)  # pyright: ignore [reportArgumentType]
            else:
                out = middleware.preprocess(app=self, state=state, event=event)  # pyright: ignore [reportArgumentType]
            if out is not None:
                return out  # pyright: ignore [reportReturnType]

    async def _postprocess(
        self, state: BaseState, event: Event, update: StateUpdate
    ) -> StateUpdate:
        """Postprocess the event.

        This is where middleware can modify the delta after it is processed.
        Each middleware is called in the order it was added to the app.

        Args:
            state: The state to postprocess.
            event: The event to postprocess.
            update: The current state update.

        Returns:
            The state update to return.
        """
        for middleware in self.middleware:
            if asyncio.iscoroutinefunction(middleware.postprocess):
                out = await middleware.postprocess(
                    app=self,  # pyright: ignore [reportArgumentType]
                    state=state,
                    event=event,
                    update=update,
                )
            else:
                out = middleware.postprocess(
                    app=self,  # pyright: ignore [reportArgumentType]
                    state=state,
                    event=event,
                    update=update,
                )
            if out is not None:
                return out  # pyright: ignore [reportReturnType]
        return update
