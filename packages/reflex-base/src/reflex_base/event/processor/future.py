"""EventFuture: a future that tracks child futures for hierarchical event processing."""

from __future__ import annotations

import asyncio
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

    # Child futures spawned by this future, if any. Excluded from the repr so
    # logging a future never recurses through an arbitrarily deep chain.
    children: list[EventFuture] = dataclasses.field(default_factory=list, repr=False)

    # The parent future that spawned this one, or None if this future was
    # enqueued directly from the queue rather than chained from another event.
    parent: EventFuture | None = dataclasses.field(default=None, repr=False)

    # The event loop that this future is running on.
    loop: asyncio.AbstractEventLoop = dataclasses.field(
        default_factory=asyncio.get_running_loop, repr=False
    )

    # Key under which this future is registered for latest-wins supersession
    # in the EventProcessor, if any.
    supersede_key: tuple[str, str] | None = dataclasses.field(default=None, repr=False)

    # Generation stamp of the user-initiated root enqueue this future's chain
    # belongs to; chained futures inherit it from their parent, so comparing
    # stamps orders invocations by user action rather than enqueue time.
    root_gen: int = dataclasses.field(default=0, repr=False)

    # Supersession keys for which an ancestor invocation in this chain is
    # already registered; a covered invocation is not re-registered, keeping
    # a self-chaining handler's registration at its first invocation.
    covered_supersede_keys: frozenset[tuple[str, str]] = dataclasses.field(
        default=frozenset(), repr=False
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

        Walks the tree iteratively: a self-chaining handler (e.g. a polling
        loop) nests one level deeper per tick, so recursion would exceed the
        interpreter's recursion limit.

        Returns:
            True if this future and all descendants have completed.
        """
        if not self.done():
            return False
        stack = list(self.children)
        while stack:
            future = stack.pop()
            if not future.done():
                return False
            stack.extend(future.children)
        return True

    async def wait_all(self) -> Any:
        """Wait for this future and all descendant futures to complete.

        Walks each children list by index so that children added after
        iteration begins are still awaited, using an explicit stack so an
        arbitrarily deep chain never exceeds the recursion limit.

        Child exceptions are suppressed since they are handled independently
        by the event processor's _finish_task callback. Descendants of a
        child that failed or was cancelled are not awaited.

        Returns:
            The result of this future.
        """
        result = await self
        stack: list[tuple[EventFuture, int]] = [(self, 0)]
        while stack:
            future, i = stack[-1]
            if i >= len(future.children):
                stack.pop()
                continue
            stack[-1] = (future, i + 1)
            child = future.children[i]
            try:
                await child
            except (Exception, asyncio.CancelledError):
                continue
            stack.append((child, 0))
        return result

    def cancel(self, msg: object = None) -> bool:
        """Cancel this future and all descendant futures.

        Args:
            msg: Optional cancellation message.

        Returns:
            True if the future was successfully cancelled.
        """
        result = super(EventFuture, self).cancel(msg)
        # Iterative pre-order walk so an arbitrarily deep chain never exceeds
        # the recursion limit while siblings are still cancelled in order.
        stack = self.children[::-1]
        while stack:
            child = stack.pop()
            super(EventFuture, child).cancel(msg)
            stack.extend(reversed(child.children))
        return result


__all__ = [
    "EventFuture",
]
