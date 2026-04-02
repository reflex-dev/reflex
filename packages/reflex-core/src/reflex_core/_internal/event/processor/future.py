"""EventFuture: a future that tracks child futures for hierarchical event processing."""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any


class EventFuture(asyncio.Future):
    """A future that tracks child futures for hierarchical event processing.

    When events are chained (a handler enqueues additional events), the child
    futures are tracked so callers can wait for the entire chain to complete.
    """

    children: list[EventFuture]

    def __init__(self, *, loop: asyncio.AbstractEventLoop | None = None) -> None:
        super().__init__(loop=loop)
        self.children = []

    @classmethod
    def create(cls, loop: asyncio.AbstractEventLoop | None = None) -> EventFuture:
        """Create a new EventFuture on the given or running event loop.

        Args:
            loop: The event loop to use. Defaults to the running loop.

        Returns:
            A new EventFuture instance.
        """
        if loop is None:
            loop = asyncio.get_running_loop()
        return cls(loop=loop)

    def add_child(self, child: EventFuture) -> None:
        """Add a child future to this tracked future.

        Args:
            child: The child EventFuture to add.

        Raises:
            RuntimeError: If this future is already done.
        """
        if self.done():
            msg = "Cannot add a child to an EventFuture that is already done."
            raise RuntimeError(msg)
        self.children.append(child)

    def all_done(self) -> bool:
        """Check if this future and all descendant futures are done.

        Returns:
            True if this future and all descendants have completed.
        """
        if not self.done():
            return False
        return all(child.all_done() for child in self.children)

    async def wait_all(self) -> Any:
        """Wait for this future and all descendant futures to complete.

        Walks the children list by index so that children added after
        iteration begins are still awaited.

        Child exceptions are suppressed since they are handled independently
        by the event processor's _finish_task callback.

        Returns:
            The result of this future.
        """
        result = await self
        i = 0
        while i < len(self.children):
            child = self.children[i]
            with contextlib.suppress(Exception, asyncio.CancelledError):
                await child.wait_all()
            i += 1
        return result

    def cancel(self, msg: object = None) -> bool:
        """Cancel this future and all descendant futures.

        Args:
            msg: Optional cancellation message.

        Returns:
            True if the future was successfully cancelled.
        """
        result = super().cancel(msg)
        for child in self.children:
            child.cancel(msg)
        return result


__all__ = [
    "EventFuture",
]
