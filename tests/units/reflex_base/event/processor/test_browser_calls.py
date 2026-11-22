"""Tests for the registry of browser calls the backend awaits."""

import asyncio
import json
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

PAGE_REPLACED = (
    "The browser tab reloaded or left the page before the script returned a "
    "result, so the script stopped. Catch BrowserDisconnectedError where the "
    "user may reload or leave the page while the script runs."
)


def grace_expired(grace_period: float) -> str:
    """The message of a call whose tab did not reconnect in time.

    Args:
        grace_period: The grace period, in seconds.

    Returns:
        The error message.
    """
    return (
        "The browser tab disconnected and did not reconnect within "
        f"browser_call_grace_period ({grace_period} seconds), so the script's "
        "result is lost: the tab was closed, or lost its connection. Catch "
        "BrowserDisconnectedError where the user may close the tab, or raise "
        "`browser_call_grace_period` in rxconfig.py if connections drop for "
        "longer."
    )


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
    """Start a call to the tab of page ``p1`` and wait for its event to be sent.

    Args:
        calls: The registry.
        timeout: The call's timeout.
        token: The client token.

    Returns:
        The browser, the task awaiting the call, and the call's request id.
    """
    browser = Browser()
    task = asyncio.create_task(calls.call(token, "p1", EVENT, timeout, browser.emit))
    return browser, task, await browser.rid()


async def _raised(task: asyncio.Task[Any]) -> tuple[type[BaseException], str]:
    """Await a call that fails.

    Args:
        task: The task awaiting the call.

    Returns:
        The type and message of the exception it raised.
    """
    with pytest.raises(Exception) as exc_info:
        await task
    return type(exc_info.value), str(exc_info.value)


def _assert_forgotten(calls: BrowserCalls) -> None:
    """Assert the registry holds nothing of the calls made.

    Args:
        calls: The registry.
    """
    assert (calls._futures, calls._tabs) == ({}, {})


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
    calls.resolve(rid, {"rid": rid, "json": '{"a": [1, null]}'})
    assert await task == {"a": [1, None]}
    _assert_forgotten(calls)


async def test_a_result_settles_its_call_by_request_id_once():
    """A result for an unknown rid is dropped, and the first result for a call wins."""
    calls = BrowserCalls()
    _, task, rid = await _start_call(calls)
    calls.resolve("unknown", {"json": "2"})
    await asyncio.sleep(0)
    assert not task.done()
    calls.resolve(rid, {"json": "3"})
    calls.resolve(rid, {"json": "4"})
    assert await task == 3
    _assert_forgotten(calls)


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
    calls.resolve(rid, {"rid": rid, "error": error})
    with pytest.raises(expected_type) as exc_info:
        await task
    exc = exc_info.value
    assert type(exc) is expected_type
    assert (exc.name, exc.message, exc.stack, str(exc)) == expected


def _unreadable(detail: str) -> str:
    """The message of a result the backend cannot read.

    Args:
        detail: Why it cannot be read.

    Returns:
        The error message.
    """
    return (
        f"The browser sent a result the backend cannot read ({detail}). The page "
        "runs a frontend built for another version of Reflex: rebuild the "
        "frontend (restart `reflex run`, or export the app again) and reload the "
        "page."
    )


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        (
            {},
            _unreadable(
                "the JSON object must be str, bytes or bytearray, not NoneType"
            ),
        ),
        (
            {"json": "{"},
            _unreadable(
                "Expecting property name enclosed in double quotes: line 1 column 2 "
                "(char 1)"
            ),
        ),
        (
            {"json": 5},
            _unreadable("the JSON object must be str, bytes or bytearray, not int"),
        ),
    ],
)
async def test_a_result_the_backend_cannot_read_raises_a_serialization_error(
    outcome: dict[str, Any], expected: str
):
    """A result the backend cannot parse fails the call instead of hanging it.

    Args:
        outcome: The outcome the browser sent.
        expected: The error's message.
    """
    calls = BrowserCalls()
    _, task, rid = await _start_call(calls)
    calls.resolve(rid, outcome)
    with pytest.raises(BrowserResultSerializationError) as exc_info:
        await task
    exc = exc_info.value
    assert (exc.name, exc.message, exc.stack, str(exc)) == ("", expected, "", expected)
    _assert_forgotten(calls)


async def test_a_result_too_deep_to_parse_raises_a_serialization_error(
    monkeypatch: pytest.MonkeyPatch,
):
    """A result whose nesting exhausts the parser fails the call instead of hanging it.

    The depth that exhausts it depends on the interpreter's stack, so the
    parser is made to fail the way it does at that depth.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
    """

    def exhausted(text: str) -> Any:
        raise RecursionError

    monkeypatch.setattr(json, "loads", exhausted)
    calls = BrowserCalls()
    _, task, rid = await _start_call(calls)
    calls.resolve(rid, {"json": "[[]]"})
    with pytest.raises(BrowserResultSerializationError) as exc_info:
        await task
    expected = (
        "The script returned a value nested too deeply for Python's JSON parser. "
        "Return a value with fewer levels of nested objects and arrays."
    )
    exc = exc_info.value
    assert (exc.name, exc.message, exc.stack, str(exc)) == ("", expected, "", expected)
    _assert_forgotten(calls)


async def test_call_times_out():
    """A call without a result within its timeout raises TimeoutError and is forgotten."""
    calls = BrowserCalls()
    with pytest.raises(TimeoutError) as exc_info:
        await calls.call("tok", "p1", EVENT, 0.01, Browser().emit)
    assert str(exc_info.value) == (
        "The browser did not return a result for `_call_script` within 0.01 "
        "seconds. If the script needs longer, pass a longer `timeout=` to the "
        "call (or `timeout=None` to wait without a limit) or raise "
        "`browser_call_timeout` in rxconfig.py; if it returns a promise, make "
        "sure the promise settles."
    )
    _assert_forgotten(calls)


async def test_disconnect_fails_every_call_of_the_tab_after_the_grace_period():
    """A tab that does not reconnect within the grace period fails all its calls."""
    calls = BrowserCalls()
    _, first, _ = await _start_call(calls)
    _, second, _ = await _start_call(calls)
    _, other_tab, other_rid = await _start_call(calls, token="other")
    calls.disconnect("tok", 0.01)
    failed = (BrowserDisconnectedError, grace_expired(0.01))
    assert [await _raised(first), await _raised(second)] == [failed, failed]
    assert calls._tabs.keys() == {"other"}
    calls.resolve(other_rid, {"json": "1"})
    assert await other_tab == 1
    _assert_forgotten(calls)


async def test_disconnect_without_a_grace_period_fails_the_calls_at_once():
    """A grace period of zero fails the calls on the disconnect itself, except one already settled."""
    calls = BrowserCalls()
    _, settled, rid = await _start_call(calls)
    _, unsettled, _ = await _start_call(calls)
    calls.resolve(rid, {"json": "7"})
    calls.disconnect("tok", 0)
    assert calls._tabs == {}
    assert await settled == 7
    assert await _raised(unsettled) == (BrowserDisconnectedError, grace_expired(0))
    _assert_forgotten(calls)


async def test_a_reconnect_of_the_page_within_the_grace_period_keeps_the_calls():
    """The same page load reconnecting in time still answers its calls."""
    calls = BrowserCalls()
    _, task, rid = await _start_call(calls)
    calls.disconnect("tok", 0.01)
    timer = calls._tabs["tok"].grace_timer
    calls.connect("tok", "p1")
    assert timer is not None
    assert timer.cancelled()
    assert calls._tabs["tok"].grace_timer is None
    await asyncio.sleep(0.02)
    assert not task.done()
    calls.resolve(rid, {"json": "true"})
    assert await task is True
    _assert_forgotten(calls)


async def test_a_connect_from_another_page_load_fails_the_calls_at_once():
    """A reloaded page connecting under the token means the script stopped with the old one."""
    calls = BrowserCalls()
    _, task, _ = await _start_call(calls)
    calls.disconnect("tok", 5)
    timer = calls._tabs["tok"].grace_timer
    calls.connect("tok", "p2")
    assert timer is not None
    assert timer.cancelled()
    assert await _raised(task) == (BrowserDisconnectedError, PAGE_REPLACED)
    _assert_forgotten(calls)


async def test_a_connect_while_the_tab_is_connected_keeps_its_calls():
    """A connect for a tab that never disconnected, or one without calls, changes nothing."""
    calls = BrowserCalls()
    _, task, rid = await _start_call(calls)
    calls.connect("tok", "p2")
    calls.connect("unknown", "p1")
    calls.disconnect("unknown", 5)
    assert calls._tabs.keys() == {"tok"}
    calls.resolve(rid, {"json": "1"})
    assert await task == 1
    _assert_forgotten(calls)


async def test_a_call_ending_during_the_grace_period_cancels_its_timer():
    """The last call settling, or its task cancelled, while the tab is away ends the grace period."""
    calls = BrowserCalls()
    _, settled, rid = await _start_call(calls)
    calls.disconnect("tok", 5)
    timer = calls._tabs["tok"].grace_timer
    calls.resolve(rid, {"json": "1"})
    assert await settled == 1
    assert timer is not None
    assert timer.cancelled()
    _assert_forgotten(calls)

    _, cancelled, _ = await _start_call(calls)
    calls.disconnect("tok", 5)
    timer = calls._tabs["tok"].grace_timer
    cancelled.cancel()
    with pytest.raises(asyncio.CancelledError):
        await cancelled
    assert timer is not None
    assert timer.cancelled()
    _assert_forgotten(calls)


async def test_close_cancels_pending_calls():
    """Shutting the backend down cancels the calls still waiting, and their timers."""
    calls = BrowserCalls()
    _, away, _ = await _start_call(calls)
    calls.disconnect("tok", 5)
    timer = calls._tabs["tok"].grace_timer
    _, connected, _ = await _start_call(calls, token="other")
    calls.close()
    for task in (away, connected):
        with pytest.raises(asyncio.CancelledError):
            await task
    assert timer is not None
    assert timer.cancelled()
    _assert_forgotten(calls)
