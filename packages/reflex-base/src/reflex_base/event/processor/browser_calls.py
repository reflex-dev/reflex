"""The browser calls the backend awaits: frontend events whose result it waits for."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import uuid
from collections.abc import Awaitable, Callable, Mapping
from typing import TYPE_CHECKING, Any

from reflex_base.utils.exceptions import (
    BrowserDisconnectedError,
    BrowserResultSerializationError,
    BrowserScriptError,
)

if TYPE_CHECKING:
    from reflex_base.event import Event

# The ``kind`` of the error the frontend reports for a value JSON cannot carry.
SERIALIZATION_ERROR_KIND = "serialization"


@dataclasses.dataclass(slots=True)
class BrowserCalls:
    """The browser calls waiting for a result, per client token.

    A result resolves a call only when it comes from the token the call was
    sent to, so one tab cannot answer another tab's call.
    """

    # Client token -> request id -> the future its result resolves.
    _pending: dict[str, dict[str, asyncio.Future[Any]]] = dataclasses.field(
        default_factory=dict
    )
    # Client token -> the timer that fails its calls once the grace period
    # after a disconnect is over.
    _grace_timers: dict[str, asyncio.TimerHandle] = dataclasses.field(
        default_factory=dict
    )

    async def call(
        self,
        token: str,
        event: Event,
        timeout: float | None,
        emit: Callable[[str, Event], Awaitable[Any]],
    ) -> Any:
        """Send an event to a client and wait for the result the browser sends back.

        Args:
            token: The client token to send the event to.
            event: The frontend event to run in the browser.
            timeout: Seconds to wait for the result, or None to wait until it arrives.
            emit: Sends an event to a client.

        Returns:
            The value the browser sent back.

        Raises:
            TimeoutError: If no result arrives within the timeout.
        """
        rid = uuid.uuid4().hex
        future = asyncio.get_running_loop().create_future()
        calls = self._pending.setdefault(token, {})
        calls[rid] = future
        try:
            await emit(token, dataclasses.replace(event, rid=rid))
            try:
                return await asyncio.wait_for(future, timeout)
            except TimeoutError:
                msg = (
                    f"The browser did not return a result for `{event.name}` "
                    f"within {timeout} seconds."
                )
                raise TimeoutError(msg) from None
        finally:
            calls.pop(rid, None)
            # The token's calls may have been failed on a disconnect already,
            # which drops this mapping from _pending.
            if not calls and self._pending.get(token) is calls:
                del self._pending[token]
                if (timer := self._grace_timers.pop(token, None)) is not None:
                    timer.cancel()

    def resolve(self, token: str, rid: str, outcome: Mapping[str, Any]) -> None:
        """Settle a call with the outcome the browser reported for it.

        An outcome for a call that is no longer waiting (it timed out, or the
        token never made it) is dropped.

        Args:
            token: The client token the outcome came from.
            rid: The request id of the call.
            outcome: ``{"json": <the result as JSON>}``, or ``{"error": {"name",
                "message", "stack", "kind"}}`` when the script failed.
        """
        calls = self._pending.get(token)
        if calls is None or (future := calls.pop(rid, None)) is None or future.done():
            return
        error = outcome.get("error")
        if isinstance(error, Mapping):
            error_cls = (
                BrowserResultSerializationError
                if error.get("kind") == SERIALIZATION_ERROR_KIND
                else BrowserScriptError
            )
            future.set_exception(
                error_cls(
                    str(error.get("name", "Error")),
                    str(error.get("message", "")),
                    str(error.get("stack", "")),
                )
            )
            return
        try:
            future.set_result(json.loads(outcome["json"]))
        except (KeyError, TypeError, ValueError) as e:
            future.set_exception(
                BrowserResultSerializationError(
                    type(e).__name__, f"The browser sent a malformed result: {e}"
                )
            )

    def disconnect(self, token: str, grace_period: float) -> None:
        """Start the grace period of a client's calls after it disconnected.

        The tab may reconnect within it, and its results then still arrive.

        Args:
            token: The disconnected client token.
            grace_period: Seconds to wait for the client to reconnect.
        """
        if token not in self._pending or token in self._grace_timers:
            return
        if grace_period <= 0:
            self._fail(token)
            return
        self._grace_timers[token] = asyncio.get_running_loop().call_later(
            grace_period, self._fail, token
        )

    def reconnect(self, token: str) -> None:
        """End the grace period of a client that connected again.

        Args:
            token: The reconnected client token.
        """
        if (timer := self._grace_timers.pop(token, None)) is not None:
            timer.cancel()

    def close(self) -> None:
        """Cancel every pending call, as the backend shuts down."""
        for timer in self._grace_timers.values():
            timer.cancel()
        self._grace_timers.clear()
        for calls in self._pending.values():
            for future in calls.values():
                future.cancel()
        self._pending.clear()

    def _fail(self, token: str) -> None:
        """Fail a client's calls: it did not reconnect within the grace period.

        Args:
            token: The disconnected client token.
        """
        self._grace_timers.pop(token, None)
        for future in self._pending.pop(token, {}).values():
            if not future.done():
                future.set_exception(
                    BrowserDisconnectedError(
                        "The browser tab disconnected before returning a result."
                    )
                )


__all__ = ["BrowserCalls"]
