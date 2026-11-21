"""Tests for the registry of browser calls the backend awaits."""

import asyncio
from typing import Any

import pytest
from reflex_base.event import Event
from reflex_base.event.processor.browser_calls import BrowserCalls
from reflex_base.utils.exceptions import (
    BrowserDisconnectedError,
    BrowserResultSerializationError,
    BrowserScriptError,
)

EVENT = Event(name="_call_script", payload={"javascript_code": "1", "callback": None})


class Browser:
    """Records the events sent to it, like a connected tab."""

    def __init__(self):
        """Start with nothing sent."""
        self.sent: list[tuple[str, Event]] = []
        self.received = asyncio.Event()

    async def emit(self, token: str, event: Event) -> None:
        """Record an event sent to a tab.

        Args:
            token: The client token.
            event: The event sent.
        """
        self.sent.append((token, event))
        self.received.set()

    async def rid(self) -> str:
        """Wait for the first event sent and return its request id.

        Returns:
            The request id of the event.
        """
        await self.received.wait()
        return self.sent[0][1].payload["rid"]


async def _start_call(
    calls: BrowserCalls, timeout: float | None = None, token: str = "tok"
) -> tuple[Browser, asyncio.Task[Any], str]:
    """Start a call and wait for its event to be sent.

    Args:
        calls: The registry.
        timeout: The call's timeout.
        token: The client token.

    Returns:
        The browser, the task awaiting the call, and the call's request id.
    """
    browser = Browser()
    task = asyncio.create_task(calls.call(token, EVENT, timeout, browser.emit))
    return browser, task, await browser.rid()


async def test_call_sends_the_event_with_a_request_id_and_returns_the_result():
    """The browser receives the event with a rid in its payload; its JSON result is the call's value."""
    calls = BrowserCalls()
    browser, task, rid = await _start_call(calls)
    assert browser.sent == [
        (
            "tok",
            Event(
                name="_call_script",
                payload={"javascript_code": "1", "callback": None, "rid": rid},
            ),
        )
    ]
    calls.resolve("tok", rid, {"rid": rid, "json": '{"a": [1, null]}'})
    assert await task == {"a": [1, None]}
    assert calls._pending == {}


async def test_a_result_from_another_token_or_request_is_ignored():
    """Only the tab a call was sent to can answer it, and only under its rid."""
    calls = BrowserCalls()
    _, task, rid = await _start_call(calls)
    calls.resolve("other", rid, {"json": "1"})
    calls.resolve("tok", "unknown", {"json": "2"})
    await asyncio.sleep(0)
    assert not task.done()
    calls.resolve("tok", rid, {"json": "3"})
    assert await task == 3
    # A late duplicate after the call settled is dropped.
    calls.resolve("tok", rid, {"json": "4"})


@pytest.mark.parametrize(
    ("error", "expected_type", "expected"),
    [
        (
            {"name": "TypeError", "message": "x is undefined", "stack": "at <anon>"},
            BrowserScriptError,
            ("TypeError", "x is undefined", "at <anon>", "TypeError: x is undefined"),
        ),
        (
            {
                "name": "TypeError",
                "message": "Do not know how to serialize a BigInt",
                "stack": "",
                "kind": "serialization",
            },
            BrowserResultSerializationError,
            (
                "TypeError",
                "Do not know how to serialize a BigInt",
                "",
                "TypeError: Do not know how to serialize a BigInt",
            ),
        ),
        (
            {},
            BrowserScriptError,
            ("Error", "", "", "Error: "),
        ),
    ],
)
async def test_an_error_the_browser_reports_is_raised(
    error: dict[str, str],
    expected_type: type[BrowserScriptError],
    expected: tuple[str, str, str, str],
):
    """A script error raises BrowserScriptError; a value JSON cannot carry, its subclass.

    Args:
        error: The error the browser reports.
        expected_type: The exception type the call raises.
        expected: The exception's name, message, stack and str.
    """
    calls = BrowserCalls()
    _, task, rid = await _start_call(calls)
    calls.resolve("tok", rid, {"rid": rid, "error": error})
    with pytest.raises(expected_type) as exc_info:
        await task
    exc = exc_info.value
    assert type(exc) is expected_type
    assert (exc.name, exc.message, exc.stack, str(exc)) == expected


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        ({}, "KeyError: The browser sent a malformed result: 'json'"),
        (
            {"json": "{"},
            (
                "JSONDecodeError: The browser sent a malformed result: Expecting "
                "property name enclosed in double quotes: line 1 column 2 (char 1)"
            ),
        ),
        (
            {"json": 5},
            (
                "TypeError: The browser sent a malformed result: the JSON object "
                "must be str, bytes or bytearray, not int"
            ),
        ),
    ],
)
async def test_a_malformed_result_raises_a_serialization_error(
    outcome: dict[str, Any], expected: str
):
    """A result without valid JSON fails the call instead of hanging it.

    Args:
        outcome: The malformed outcome.
        expected: The error's message.
    """
    calls = BrowserCalls()
    _, task, rid = await _start_call(calls)
    calls.resolve("tok", rid, outcome)
    with pytest.raises(BrowserResultSerializationError) as exc_info:
        await task
    assert str(exc_info.value) == expected


async def test_call_times_out():
    """A call without a result within its timeout raises TimeoutError and is forgotten."""
    calls = BrowserCalls()
    with pytest.raises(TimeoutError) as exc_info:
        await calls.call("tok", EVENT, 0.01, Browser().emit)
    assert str(exc_info.value) == (
        "The browser did not return a result for `_call_script` within 0.01 seconds."
    )
    assert calls._pending == {}


async def test_disconnect_fails_the_calls_after_the_grace_period():
    """A tab that does not reconnect within the grace period fails its calls."""
    calls = BrowserCalls()
    _, task, _ = await _start_call(calls)
    calls.disconnect("tok", 0.01)
    with pytest.raises(BrowserDisconnectedError) as exc_info:
        await task
    assert str(exc_info.value) == (
        "The browser tab disconnected before returning a result."
    )
    assert calls._pending == {}
    assert calls._grace_timers == {}


async def test_disconnect_without_a_grace_period_fails_the_calls_at_once():
    """A grace period of zero fails the calls on the disconnect itself."""
    calls = BrowserCalls()
    _, task, _ = await _start_call(calls)
    calls.disconnect("tok", 0)
    assert calls._grace_timers == {}
    with pytest.raises(BrowserDisconnectedError):
        await task


async def test_reconnect_within_the_grace_period_keeps_the_calls():
    """A tab reconnecting in time still answers its calls."""
    calls = BrowserCalls()
    _, task, rid = await _start_call(calls)
    calls.disconnect("tok", 0.01)
    calls.reconnect("tok")
    assert calls._grace_timers == {}
    await asyncio.sleep(0.02)
    assert not task.done()
    calls.resolve("tok", rid, {"json": "true"})
    assert await task is True


def test_disconnect_without_pending_calls_starts_no_timer():
    """A tab with nothing pending needs no grace period."""
    calls = BrowserCalls()
    calls.disconnect("tok", 5)
    assert calls._grace_timers == {}


async def test_settled_call_ends_the_grace_period():
    """The last call settling during the grace period cancels its timer."""
    calls = BrowserCalls()
    _, task, rid = await _start_call(calls)
    calls.disconnect("tok", 5)
    timer = calls._grace_timers["tok"]
    calls.resolve("tok", rid, {"json": "1"})
    assert await task == 1
    assert calls._grace_timers == {}
    assert timer.cancelled()


async def test_close_cancels_pending_calls():
    """Shutting the backend down cancels the calls still waiting."""
    calls = BrowserCalls()
    _, task, _ = await _start_call(calls)
    calls.disconnect("tok", 5)
    timer = calls._grace_timers["tok"]
    calls.close()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert timer.cancelled()
    assert calls._pending == {}
    assert calls._grace_timers == {}
