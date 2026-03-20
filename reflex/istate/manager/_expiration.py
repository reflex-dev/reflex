"""Internal helpers for in-memory state expiration."""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import heapq
import time
from typing import TYPE_CHECKING, ClassVar

from . import _default_token_expiration

if TYPE_CHECKING:
    from reflex.state import BaseState


@dataclasses.dataclass
class StateManagerExpiration:
    """Internal base for managers with in-memory state expiration."""

    _locked_expiration_poll_interval: ClassVar[float] = 0.1  # 100 ms
    _recheck_expired_locks_on_unlock: ClassVar[bool] = False

    token_expiration: int = dataclasses.field(default_factory=_default_token_expiration)

    # The mapping of client ids to states.
    states: dict[str, BaseState] = dataclasses.field(default_factory=dict)

    # The dict of mutexes for each client.
    _states_locks: dict[str, asyncio.Lock] = dataclasses.field(
        default_factory=dict,
        init=False,
    )

    # The latest expiration deadline for each token.
    _token_expires_at: dict[str, float] = dataclasses.field(
        default_factory=dict,
        init=False,
    )

    # Deadline-ordered token expiration heap.
    _token_expiration_heap: list[tuple[float, str]] = dataclasses.field(
        default_factory=list,
        init=False,
        repr=False,
    )

    # Tokens whose expiration is deferred until their state lock is released.
    _pending_locked_expirations: set[str] = dataclasses.field(
        default_factory=set,
        init=False,
        repr=False,
    )

    # Wake any background expiration worker when token activity changes.
    _token_activity: asyncio.Event = dataclasses.field(
        default_factory=asyncio.Event,
        init=False,
        repr=False,
    )

    _scheduled_expiration_deadline: float | None = dataclasses.field(
        default=None,
        init=False,
        repr=False,
    )

    def _touch_token(self, token: str):
        """Record access for a token.

        Args:
            token: The token that was accessed.
        """
        touched_at = time.time()
        expires_at = touched_at + self.token_expiration  # seconds from last touch
        self._token_expires_at[token] = expires_at
        self._pending_locked_expirations.discard(token)
        heapq.heappush(self._token_expiration_heap, (expires_at, token))
        if (
            self._scheduled_expiration_deadline is None
            or expires_at <= self._scheduled_expiration_deadline
        ):
            self._token_activity.set()

    def _maybe_compact_expiration_heap(self):
        """Rebuild the heap when stale deadline entries accumulate."""
        if len(self._token_expiration_heap) <= (2 * len(self._token_expires_at)) + 1:
            return
        self._token_expiration_heap = [
            (expires_at, token)
            for token, expires_at in self._token_expires_at.items()
            if token not in self._pending_locked_expirations
        ]
        heapq.heapify(self._token_expiration_heap)

    def _next_expiration(self) -> tuple[float, str] | None:
        """Get the next valid token expiration from the heap.

        Returns:
            The next expiration deadline and token, or None if there are no
            active deadlines to process.
        """
        while self._token_expiration_heap:
            expires_at, token = self._token_expiration_heap[0]
            current_expiration = self._token_expires_at.get(token)
            if (
                current_expiration != expires_at
                or token in self._pending_locked_expirations
            ):
                heapq.heappop(self._token_expiration_heap)
                continue
            return expires_at, token
        return None

    def _purge_token(self, token: str):
        """Remove a token from all in-memory expiration bookkeeping.

        Args:
            token: The token to purge.
        """
        self._token_expires_at.pop(token, None)
        self.states.pop(token, None)
        self._states_locks.pop(token, None)
        self._pending_locked_expirations.discard(token)

    def _purge_expired_tokens(
        self,
        now: float | None = None,
    ):
        """Purge expired in-memory state entries.

        If a token's state lock is currently held, defer cleanup until a later pass
        to avoid replacing the state while it is being modified.

        Args:
            now: The time to compare against.
        """
        now = time.time() if now is None else now
        while (
            next_expiration := self._next_expiration()
        ) is not None and next_expiration[0] <= now:
            _expires_at, token = heapq.heappop(self._token_expiration_heap)
            if (
                state_lock := self._states_locks.get(token)
            ) is not None and state_lock.locked():
                self._pending_locked_expirations.add(token)
                continue
            self._purge_token(token)
        self._maybe_compact_expiration_heap()

    def _next_expiration_in(
        self,
        now: float | None = None,
    ) -> float | None:
        """Get the delay until the next expiration check should run.

        Args:
            now: The time to compare against.

        Returns:
            The number of seconds until the next check, or None when there are no
            tracked tokens.
        """
        if (next_expiration := self._next_expiration()) is None:
            if (
                self._pending_locked_expirations
                and not self._recheck_expired_locks_on_unlock
            ):
                return self._locked_expiration_poll_interval
            return None

        now = time.time() if now is None else now
        next_delay = max(0.0, next_expiration[0] - now)
        if (
            self._pending_locked_expirations
            and not self._recheck_expired_locks_on_unlock
        ):
            return min(next_delay, self._locked_expiration_poll_interval)
        return next_delay

    def _reset_token_activity_wait(self):
        """Reset the token activity event before waiting."""
        self._token_activity.clear()

    def _prepare_expiration_wait(
        self,
        *,
        now: float | None = None,
        default_timeout: float | None = None,
    ) -> float | None:
        """Prepare the next wait window for an expiration worker.

        Args:
            now: The current time.
            default_timeout: A fallback timeout when there are no in-memory token
                deadlines to wait on.

        Returns:
            The timeout to use for the next wait.
        """
        self._reset_token_activity_wait()
        now = time.time() if now is None else now
        timeout = self._next_expiration_in(now=now)
        if timeout is None:
            timeout = default_timeout
        elif default_timeout is not None:
            timeout = min(timeout, default_timeout)
        self._scheduled_expiration_deadline = None if timeout is None else now + timeout
        return timeout

    def _notify_token_unlocked(self, token: str):
        """Requeue a deferred expiration check for a token after its lock is released.

        Args:
            token: The unlocked token.
        """
        if token not in self._pending_locked_expirations:
            return
        self._pending_locked_expirations.discard(token)
        if (expires_at := self._token_expires_at.get(token)) is None:
            return
        heapq.heappush(self._token_expiration_heap, (expires_at, token))
        self._token_activity.set()

    async def _wait_for_token_activity(self, timeout: float | None):
        """Wait for token activity or a timeout.

        Args:
            timeout: The maximum time to wait. When None, waits indefinitely.
        """
        try:
            if timeout is None:
                await self._token_activity.wait()
                return
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._token_activity.wait(), timeout=timeout)
        finally:
            self._scheduled_expiration_deadline = None
