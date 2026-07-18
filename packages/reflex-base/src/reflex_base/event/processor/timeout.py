"""DrainTimeoutManager: manages an optional combined timeout over multiple calls."""

from __future__ import annotations

import dataclasses
import time


@dataclasses.dataclass(kw_only=True, slots=True)
class DrainTimeoutManager:
    """Manages an optional combined timeout over multiple calls.

    Each time the context is entered, yield the remaining time until the
    overall timeout is reached, or 0 if the timeout has already been reached.
    This allows multiple operations to share a single overall timeout, even if
    they are not executed sequentially.
    """

    drain_deadline: float | None = None

    @classmethod
    def with_timeout(cls, timeout: float | None) -> DrainTimeoutManager:
        """Create a DrainTimeoutManager with a specified timeout.

        Args:
            timeout: The overall amount of time in seconds to wait.

        Returns:
            A DrainTimeoutManager instance with the drain deadline set.
        """
        if timeout is None:
            return cls(drain_deadline=None)
        return cls(drain_deadline=time.time() + timeout)

    def __enter__(self) -> float:
        """Enter the context and yield the remaining time.

        Returns:
            The remaining time in seconds until the overall timeout is reached, or 0 if the timeout
            has already been reached.
        """
        if self.drain_deadline is not None:
            return max(0, self.drain_deadline - time.time())
        return 0

    def __exit__(self, *exc_info) -> None:
        """Exit the context. No cleanup necessary."""


__all__ = [
    "DrainTimeoutManager",
]
