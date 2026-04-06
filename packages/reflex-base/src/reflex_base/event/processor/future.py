"""EventFuture: a future that tracks child futures for hierarchical event processing."""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
from typing import Any


@dataclasses.dataclass(kw_only=True, slots=True, eq=False)
class EventFuture(asyncio.Future):
    """A future that tracks child futures for hierarchical event processing.

    When events are chained (a handler enqueues additional events), the child
    futures are tracked so callers can wait for the entire chain to complete.
    """

    # The transaction id associated with this future.
    txid: str

    # Child futures spawned by this future, if any.
    children: list[EventFuture] = dataclasses.field(default_factory=list)

    # The parent future that spawned this one, or None if this future was
    # enqueued directly from the queue rather than chained from another event.
    parent: EventFuture | None = dataclasses.field(default=None, repr=False)

    # The event loop that this future is running on.
    loop: asyncio.AbstractEventLoop = dataclasses.field(
        default_factory=asyncio.get_running_loop, repr=False
    )

    def __post_init__(self) -> None:
        """Call Future.__init__ for the EventFuture."""
        super(EventFuture, self).__init__(loop=self.loop)

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
        result = super(EventFuture, self).cancel(msg)
        for child in self.children:
            child.cancel(msg)
        return result


__all__ = [
    "EventFuture",
]
