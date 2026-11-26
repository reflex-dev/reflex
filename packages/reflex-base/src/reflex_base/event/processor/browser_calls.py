"""The browser calls the backend awaits: frontend events whose result it waits for."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import uuid
from collections.abc import Awaitable, Callable, Mapping
from typing import TYPE_CHECKING, Any, NewType

from reflex_base.utils.exceptions import (
    BrowserDisconnectedError,
    BrowserResultSerializationError,
    BrowserScriptError,
)

if TYPE_CHECKING:
    from reflex_base.event import Event

# The three ids a browser call is addressed by, kept apart so that passing one
# for another is a type error.
ClientToken = NewType("ClientToken", str)
# The page load a tab connected from; a reload gives it a new one.
PageId = NewType("PageId", str)
# The random id a call's event carries and its result echoes.
RequestId = NewType("RequestId", str)

# The ``kind`` of the error the frontend reports for a value JSON cannot carry.
SERIALIZATION_ERROR_KIND = "serialization"

# The payload key of a browser call's request id (must match state.js).
RID_KEY = "rid"

_PAGE_REPLACED = (
    "The browser tab reloaded or left the page before the script returned a "
    "result, so the script stopped. Catch BrowserDisconnectedError where the "
    "user may reload or leave the page while the script runs."
)


@dataclasses.dataclass(slots=True)
class _Tab:
    """The calls awaiting the results of one client token's tab."""

    # The token the calls are filed under; a reconnect can give it a new one.
    token: ClientToken
    # The page load the calls were sent to: a script stops with its page.
    page: PageId
    rids: set[RequestId] = dataclasses.field(default_factory=set)
    # Set while the tab is disconnected; fails the calls unless it reconnects.
    grace_timer: asyncio.TimerHandle | None = None


@dataclasses.dataclass(slots=True)
class BrowserCalls:
    """The browser calls waiting for a result.

    A result settles the call with its request id, whichever socket it comes
    from: the id is random and only ever sent to the tab the call runs in,
    which may have been given a new token when it reconnected.
    """

    _futures: dict[RequestId, asyncio.Future[Any]] = dataclasses.field(
        default_factory=dict
    )
    # Client token -> the calls sent to its tab, failed when it goes away.
    _tabs: dict[ClientToken, _Tab] = dataclasses.field(default_factory=dict)

    async def call(
        self,
        token: ClientToken,
        page: PageId,
        event: Event,
        timeout: float | None,
        emit: Callable[[str, Event], Awaitable[Any]],
    ) -> Any:
        """Send an event to a client and wait for the result the browser sends back.

        Args:
            token: The client token to send the event to.
            page: The page load the token's tab connected from.
            event: The frontend event to run in the browser.
            timeout: Seconds to wait for the result, or None to wait until it arrives.
            emit: Sends an event to a client.

        Returns:
            The value the browser sent back.

        Raises:
            TimeoutError: If no result arrives within the timeout.
        """
        rid = RequestId(uuid.uuid4().hex)
        future = self._futures[rid] = asyncio.get_running_loop().create_future()
        tab = self._tabs.get(token)
        if tab is None:
            tab = self._tabs[token] = _Tab(token, page)
        tab.rids.add(rid)
        try:
            # Only the browser-call events carry a request id, in their
            # payload, so no other event pays for it.
            await emit(
                token,
                dataclasses.replace(event, payload={**event.payload, RID_KEY: rid}),
            )
            try:
                return await asyncio.wait_for(future, timeout)
            except TimeoutError:
                msg = (
                    f"The browser did not return a result for `{event.name}` "
                    f"within {timeout} seconds. If the script needs longer, pass "
                    "a longer `timeout=` to the call (or `timeout=None` to wait "
                    "without a limit) or raise `browser_call_timeout` in "
                    "rxconfig.py; if it returns a promise, make sure the "
                    "promise settles. A frontend built by an older version of "
                    "Reflex never returns a result: rebuild the frontend "
                    "(restart `reflex run`, or export the app again) and "
                    "reload the page."
                )
                raise TimeoutError(msg) from None
        finally:
            del self._futures[rid]
            tab.rids.remove(rid)
            # A disconnect may have failed the tab's calls already, and a new
            # call made a new _Tab for the token.
            if not tab.rids and self._tabs.get(tab.token) is tab:
                del self._tabs[tab.token]
                if tab.grace_timer is not None:
                    tab.grace_timer.cancel()

    def resolve(self, rid: RequestId, outcome: Mapping[str, Any]) -> None:
        """Settle a call with the outcome the browser reported for it.

        An outcome for a call that is no longer waiting (it timed out, or was
        never made) is dropped.

        Args:
            rid: The request id of the call.
            outcome: ``{"json": <the result as UTF-8 JSON bytes>}``, or
                ``{"error": {"name", "message", "stack", "kind"}}`` when the
                script failed.
        """
        future = self._futures.get(rid)
        if future is None or future.done():
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
            # A missing or non-string field raises the TypeError reported below.
            future.set_result(json.loads(outcome.get("json")))  # pyright: ignore[reportArgumentType]
        except (TypeError, ValueError) as e:
            future.set_exception(
                BrowserResultSerializationError(
                    "",
                    f"The browser sent a result the backend cannot read ({e}). "
                    "The page runs a frontend built for another version of "
                    "Reflex: rebuild the frontend (restart `reflex run`, or "
                    "export the app again) and reload the page.",
                )
            )
        except RecursionError:
            future.set_exception(
                BrowserResultSerializationError(
                    "",
                    "The script returned a value nested too deeply for Python's "
                    "JSON parser. Return a value with fewer levels of nested "
                    "objects and arrays.",
                )
            )

    def disconnect(self, token: ClientToken, grace_period: float) -> None:
        """Start the grace period of a client's calls after it disconnected.

        Its tab may reconnect to this worker within it, and its results then
        still arrive; a tab that reconnects to another worker sends its result
        there, and this worker never hears of it. A refused connect disconnects it again without restarting the grace
        period: a tab whose connects keep failing would otherwise hold its
        calls forever.

        Args:
            token: The disconnected client token.
            grace_period: Seconds to wait for the client to reconnect.
        """
        if (tab := self._tabs.get(token)) is None or tab.grace_timer is not None:
            return
        msg = (
            "The browser tab did not reconnect to this backend worker within "
            f"browser_call_grace_period ({grace_period} seconds), so the script's "
            "result is lost: the tab was closed, lost its connection for longer, "
            "or reconnected to another backend worker, which cannot pass the "
            "result on. Catch BrowserDisconnectedError where the user may close "
            "the tab, raise `browser_call_grace_period` in rxconfig.py if "
            "connections drop for longer, and with several backend workers route "
            "each tab to one worker (sticky sessions)."
        )
        if grace_period <= 0:
            self._fail(tab, msg)
        else:
            tab.grace_timer = asyncio.get_running_loop().call_later(
                grace_period, self._fail, tab, msg
            )

    def connecting(
        self, token: ClientToken, page: PageId, new_token: ClientToken | None = None
    ) -> None:
        """Fail a client's calls at once when it connects from another page load.

        The page the calls run in reloaded or navigated away. Calls of the
        same page keep waiting, in their grace period until the connect is
        accepted. A connect given a new token, because the token's old socket
        is still linked, moves the calls of its page to the new token, so the
        old socket's disconnect does not fail them. Another page load given a
        new token while the tab is connected is a duplicated tab, and leaves
        the calls with their tab; once the tab disconnected, the token is
        linked only until its unlinking completes, and the connect is a reload.

        Args:
            token: The client token the tab connects with.
            page: The page load it connects from.
            new_token: The token the connection was given instead, if any.
        """
        if (tab := self._tabs.get(token)) is None:
            return
        if tab.page != page:
            if new_token is None or tab.grace_timer is not None:
                self._fail(tab, _PAGE_REPLACED)
        elif new_token is not None:
            tab.token = new_token
            self._tabs[new_token] = self._tabs.pop(token)

    def connected(self, token: ClientToken) -> None:
        """End the grace period of a client whose connect was accepted.

        Args:
            token: The connected client token.
        """
        if (tab := self._tabs.get(token)) is not None and tab.grace_timer is not None:
            tab.grace_timer.cancel()
            tab.grace_timer = None

    def close(self) -> None:
        """Cancel every pending call, as the backend shuts down.

        Each call forgets itself and cancels its tab's grace timer as it ends.
        """
        for future in self._futures.values():
            future.cancel()

    def _fail(self, tab: _Tab, message: str) -> None:
        """Fail a tab's calls with BrowserDisconnectedError.

        Args:
            tab: The tab.
            message: The error's message.
        """
        del self._tabs[tab.token]
        if tab.grace_timer is not None:
            tab.grace_timer.cancel()
        for rid in tab.rids:
            # A result may have settled the call, which has not resumed yet.
            if not (future := self._futures[rid]).done():
                future.set_exception(BrowserDisconnectedError(message))


__all__ = ["BrowserCalls", "ClientToken", "PageId", "RequestId"]
