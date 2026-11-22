"""Tests for the registry of browser calls the backend awaits."""

import asyncio
import dataclasses
import json
from collections import deque
from collections.abc import Callable, Coroutine
from typing import Any, cast

import pytest
from reflex_base.event import Event
from reflex_base.event.processor.browser_calls import (
    BrowserCalls,
    ClientToken,
    PageId,
    RequestId,
)
from reflex_base.utils.exceptions import (
    BrowserDisconnectedError,
    BrowserResultSerializationError,
    BrowserScriptError,
)

EVENT = Event(name="_call_script", payload={"javascript_code": "1", "callback": None})
TOKEN = ClientToken("tok")
OTHER_TOKEN = ClientToken("other")
P1 = PageId("p1")
P2 = PageId("p2")

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

    async def rid(self) -> RequestId:
        """Wait for the first event sent and return its request id.

        Returns:
            The request id of the event.
        """
        await self.received.wait()
        return self.sent[0][1].payload["rid"]


async def _start_call(
    calls: BrowserCalls, timeout: float | None = None, token: ClientToken = TOKEN
) -> tuple[Browser, asyncio.Task[Any], RequestId]:
    """Start a call to the tab of page ``p1`` and wait for its event to be sent.

    Args:
        calls: The registry.
        timeout: The call's timeout.
        token: The client token.

    Returns:
        The browser, the task awaiting the call, and the call's request id.
    """
    browser = Browser()
    task = asyncio.create_task(calls.call(token, P1, EVENT, timeout, browser.emit))
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
    calls.resolve(RequestId("unknown"), {"json": "2"})
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
        await calls.call(TOKEN, P1, EVENT, 0.01, Browser().emit)
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
    _, other_tab, other_rid = await _start_call(calls, token=OTHER_TOKEN)
    calls.disconnect(TOKEN, 0.01)
    failed = (BrowserDisconnectedError, grace_expired(0.01))
    assert [await _raised(first), await _raised(second)] == [failed, failed]
    assert calls._tabs.keys() == {OTHER_TOKEN}
    calls.resolve(other_rid, {"json": "1"})
    assert await other_tab == 1
    _assert_forgotten(calls)


async def test_disconnect_without_a_grace_period_fails_the_calls_at_once():
    """A grace period of zero fails the calls on the disconnect itself, except one already settled."""
    calls = BrowserCalls()
    _, settled, rid = await _start_call(calls)
    _, unsettled, _ = await _start_call(calls)
    calls.resolve(rid, {"json": "7"})
    calls.disconnect(TOKEN, 0)
    assert calls._tabs == {}
    assert await settled == 7
    assert await _raised(unsettled) == (BrowserDisconnectedError, grace_expired(0))
    _assert_forgotten(calls)


async def test_the_grace_period_runs_until_a_connect_of_the_page_is_accepted():
    """The same page load reconnecting in time still answers its calls; a refused connect does not restart the wait."""
    calls = BrowserCalls()
    _, task, rid = await _start_call(calls)
    calls.disconnect(TOKEN, 0.01)
    timer = calls._tabs[TOKEN].grace_timer
    assert timer is not None
    calls.connecting(TOKEN, P1)
    # The connect is refused.
    calls.disconnect(TOKEN, 0.01)
    assert calls._tabs[TOKEN].grace_timer is timer
    assert not timer.cancelled()
    calls.connecting(TOKEN, P1)
    calls.connected(TOKEN)
    assert timer.cancelled()
    assert calls._tabs[TOKEN].grace_timer is None
    await asyncio.sleep(0.02)
    assert not task.done()
    calls.resolve(rid, {"json": "true"})
    assert await task is True
    _assert_forgotten(calls)


async def test_a_connect_from_another_page_load_fails_the_calls_at_once():
    """A reloaded page connecting under the token means the script stopped with the old one."""
    calls = BrowserCalls()
    _, task, _ = await _start_call(calls)
    calls.disconnect(TOKEN, 5)
    timer = calls._tabs[TOKEN].grace_timer
    calls.connecting(TOKEN, P2)
    assert timer is not None
    assert timer.cancelled()
    assert await _raised(task) == (BrowserDisconnectedError, PAGE_REPLACED)
    _assert_forgotten(calls)


async def test_connect_events_without_a_grace_period_change_nothing():
    """A token without calls, or a tab whose connect started its calls, is left as it is."""
    calls = BrowserCalls()
    _, task, rid = await _start_call(calls)
    unknown = ClientToken("unknown")
    calls.connecting(unknown, P1)
    calls.connected(unknown)
    calls.disconnect(unknown, 5)
    calls.connecting(TOKEN, P1)
    calls.connected(TOKEN)
    assert calls._tabs.keys() == {TOKEN}
    assert calls._tabs[TOKEN].grace_timer is None
    calls.resolve(rid, {"json": "1"})
    assert await task == 1
    _assert_forgotten(calls)


async def test_a_call_ending_during_the_grace_period_cancels_its_timer():
    """The last call settling, or its task cancelled, while the tab is away ends the grace period."""
    calls = BrowserCalls()
    _, settled, rid = await _start_call(calls)
    calls.disconnect(TOKEN, 5)
    timer = calls._tabs[TOKEN].grace_timer
    calls.resolve(rid, {"json": "1"})
    assert await settled == 1
    assert timer is not None
    assert timer.cancelled()
    _assert_forgotten(calls)

    _, cancelled, _ = await _start_call(calls)
    calls.disconnect(TOKEN, 5)
    timer = calls._tabs[TOKEN].grace_timer
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
    calls.disconnect(TOKEN, 5)
    timer = calls._tabs[TOKEN].grace_timer
    _, connected, _ = await _start_call(calls, token=OTHER_TOKEN)
    calls.close()
    for task in (away, connected):
        with pytest.raises(asyncio.CancelledError):
            await task
    assert timer is not None
    assert timer.cancelled()
    _assert_forgotten(calls)


class _Timer:
    """A grace timer that fires only when the exploration fires it."""

    def __init__(self, callback: Callable[..., None], args: tuple[Any, ...]):
        """Schedule a callback.

        Args:
            callback: The function the timer calls.
            args: Its arguments.
        """
        self.callback = callback
        self.args = args
        self.live = True

    def cancel(self) -> None:
        """Cancel the timer."""
        self.live = False

    def fire(self) -> None:
        """Run the callback, as the event loop does when the timer is due."""
        self.live = False
        self.callback(*self.args)


@dataclasses.dataclass
class _Call:
    """An awaited call whose coroutine is stepped by hand instead of by a task."""

    coro: Coroutine[Any, Any, Any]
    rid: RequestId
    future: asyncio.Future[Any]
    page: int
    # The _Tab its token had once it started.
    tab: Any
    result_sent: bool = False
    # What the call returns or raises, known once its future settles.
    outcome: tuple[Any, ...] | None = None
    ended: bool = False


class _Interleaving:
    """One token's tab and its calls, driven one event at a time.

    The socket events call BrowserCalls the way EventNamespace does: a connect
    runs ``connecting`` and then the boot event, which accepts the connect
    (``connected``) or refuses it (``disconnect``, as a disconnect does).
    """

    def __init__(self, grace: float, timers: list[_Timer]):
        """Start with the tab connected from its first page and no calls.

        Args:
            grace: The grace period.
            timers: Where the grace timers BrowserCalls schedules are recorded.
        """
        self.calls = BrowserCalls()
        self.grace = grace
        self.timers = timers
        timers.clear()
        self.socket = "connected"
        self.page = 0
        self.closed = False
        self.started: list[_Call] = []
        # The request id of the last call the tab received.
        self.rid = RequestId("")

    def actions(self) -> list[tuple[str, int]]:
        """List the events that can happen next.

        Returns:
            Each event's name and the index of the call it concerns, or -1.
        """
        socket = self.socket
        enabled = {
            "call": not self.closed and len(self.started) < 2 and socket != "gone",
            "disconnect": socket == "connected",
            "reload": socket == "gone" and self.page == 0,
            "connect": socket == "gone",
            "boot": socket == "booting",
            "refuse": socket == "booting",
            "fire": any(timer.live for timer in self.timers),
            "close": not self.closed,
        }
        actions = [(name, -1) for name, on in enabled.items() if on]
        for i, call in enumerate(self.started):
            if (
                not call.result_sent
                and socket == "connected"
                and call.page == self.page
            ):
                actions.append(("result", i))
            if not call.ended:
                actions.append(("abort" if call.outcome is None else "end", i))
        return actions

    def apply(self, name: str, i: int) -> None:
        """Run an event and check every invariant after it.

        Args:
            name: The event.
            i: The index of the call it concerns.
        """
        pending = [call for call in self.started if call.outcome is None]
        settles, outcome = self._effect(name, i, pending)
        tab = self.calls._tabs.get(TOKEN)
        timer = _grace_timer(tab)
        getattr(self, f"_{name}")(i)
        assert [call for call in pending if call.future.done()] == settles
        for call in settles:
            call.outcome = outcome
        if timer is not None and name != "boot" and self.calls._tabs.get(TOKEN) is tab:
            # Only an accepted connect ends the grace period of a tab.
            assert timer.live
        self._check()

    def _effect(
        self, name: str, i: int, pending: list[_Call]
    ) -> tuple[list[_Call], tuple[Any, ...]]:
        """Predict the calls an event settles, and how they end.

        Args:
            name: The event.
            i: The index of the call it concerns.
            pending: The calls not settled yet.

        Returns:
            The calls it settles, and what each then returns or raises.
        """
        expired = ("disconnected", grace_expired(self.grace))
        match name:
            case "result":
                return [c for c in pending if c is self.started[i]], ("returned", i)
            case "abort":
                return [self.started[i]], ("cancelled",)
            case "close":
                return pending, ("cancelled",)
            case "fire":
                return pending, expired
            case "disconnect" | "refuse":
                return (pending if self.grace == 0 else []), expired
            case "connect":
                replaced = [c for c in pending if c.page != self.page]
                return replaced, ("disconnected", PAGE_REPLACED)
        return [], ()

    async def _emit(self, token: str, event: Event) -> None:
        """Deliver a call's event to the tab, which keeps its request id.

        Args:
            token: The client token.
            event: The event.
        """
        self.rid = event.payload["rid"]

    def _call(self, i: int) -> None:
        coro = self.calls.call(TOKEN, PageId(f"p{self.page}"), EVENT, None, self._emit)
        future = coro.send(None)
        assert future is self.calls._futures[self.rid]
        self.started.append(
            _Call(coro, self.rid, future, self.page, self.calls._tabs[TOKEN])
        )

    def _result(self, i: int) -> None:
        self.started[i].result_sent = True
        self.calls.resolve(self.started[i].rid, {"json": str(i)})

    def _abort(self, i: int) -> None:
        # A timeout or a cancelled task cancels the future the call awaits.
        self.started[i].future.cancel()

    def _end(self, i: int) -> None:
        call = self.started[i]
        call.ended = True
        assert _resume(call.coro) == call.outcome

    def _disconnect(self, i: int) -> None:
        self.socket = "gone"
        self.calls.disconnect(TOKEN, self.grace)

    _refuse = _disconnect

    def _reload(self, i: int) -> None:
        self.page += 1

    def _connect(self, i: int) -> None:
        self.socket = "booting"
        self.calls.connecting(TOKEN, PageId(f"p{self.page}"))

    def _boot(self, i: int) -> None:
        self.socket = "connected"
        self.calls.connected(TOKEN)

    def _fire(self, i: int) -> None:
        next(timer for timer in self.timers if timer.live).fire()

    def _close(self, i: int) -> None:
        self.closed = True
        self.calls.close()

    def _check(self) -> None:
        """Assert the registry holds exactly the unended calls, none stranded."""
        unended = [call for call in self.started if not call.ended]
        assert self.calls._futures == {call.rid: call.future for call in unended}
        tab = self.calls._tabs.get(TOKEN)
        in_tab = [call for call in unended if call.tab is tab]
        if tab is not None:
            assert tab.rids == {call.rid for call in in_tab} != set()
            assert {call.page for call in in_tab} == {int(tab.page[1:])}
        timer = _grace_timer(tab)
        assert [t for t in self.timers if t.live] == ([] if timer is None else [timer])
        assert timer is None or self.socket != "connected"
        for call in unended:
            if call.outcome is None:
                assert call.tab is tab
                assert timer or (self.socket != "gone" and call.page == self.page)

    def key(self) -> tuple[Any, ...]:
        """Describe the state, so a state reached twice is explored once.

        Returns:
            Everything that decides what can happen next.
        """
        tab = self.calls._tabs.get(TOKEN)
        return (
            self.socket,
            self.page,
            self.closed,
            tab and (tab.page, _grace_timer(tab) is not None),
            tuple(
                (c.page, c.result_sent, c.outcome, c.ended, c.tab is tab)
                for c in self.started
            ),
        )

    def discard(self) -> None:
        """Drop the calls still running without leaving errors unretrieved."""
        for call in self.started:
            call.coro.close()
            if call.future.done() and not call.future.cancelled():
                call.future.exception()


def _grace_timer(tab: Any) -> _Timer | None:
    """Get the grace timer of a tab, while it runs.

    Args:
        tab: The _Tab, or None.

    Returns:
        The timer, or None when the tab is gone or not in a grace period.
    """
    timer = cast("_Timer | None", tab and tab.grace_timer)
    return timer if timer is not None and timer.live else None


def _resume(coro: Coroutine[Any, Any, Any]) -> tuple[Any, ...]:
    """Resume a call whose future settled, as its task would.

    Args:
        coro: The call's coroutine.

    Returns:
        What the call returned or raised.

    Raises:
        AssertionError: If the call awaits again.
    """
    try:
        awaited = coro.send(None)
    except StopIteration as stop:
        return ("returned", stop.value)
    except asyncio.CancelledError:
        return ("cancelled",)
    except BrowserDisconnectedError as e:
        return ("disconnected", str(e))
    msg = f"The call awaited {awaited!r} again after its future settled."
    raise AssertionError(msg)


_Path = tuple[tuple[str, int], ...]


@pytest.mark.parametrize(("grace", "states"), [(0, (3068, 18)), (5, (4324, 20))])
# BrowserCalls needs a running loop, although the calls are stepped by hand.
async def test_every_interleaving_settles_each_call_once_and_forgets_it(  # noqa: RUF029
    grace: float, states: tuple[int, int], monkeypatch: pytest.MonkeyPatch
):
    """Explore every order of events for one tab and two calls; the invariants hold after each.

    The events: a call starts; the page it was sent to returns its result;
    the call times out or its task is cancelled; the awaiting task resumes;
    the tab disconnects, reloads, reconnects (and its boot event succeeds or
    refuses the connect); the grace timer fires; the backend closes. Each
    state is explored once, until no new state is reached.

    Args:
        grace: The grace period; zero fails the calls on the disconnect.
        states: The number of distinct states reached, and the most events
            it takes to reach one.
        monkeypatch: The pytest monkeypatch fixture.
    """
    timers: list[_Timer] = []

    def schedule(delay: float, callback: Callable[..., None], *args: Any) -> _Timer:
        assert delay == grace
        timers.append(timer := _Timer(callback, args))
        return timer

    monkeypatch.setattr(asyncio.get_running_loop(), "call_later", schedule)

    def replay(path: _Path) -> _Interleaving:
        run = _Interleaving(grace, timers)
        for action in path:
            run.apply(*action)
        return run

    start = replay(())
    seen = {start.key()}
    # Breadth first: each state's shortest path, and the events it enables.
    queue: deque[tuple[_Path, list[tuple[str, int]]]] = deque([((), start.actions())])
    depth = 0
    while queue:
        path, actions = queue.popleft()
        depth = len(path)
        for action in actions:
            run = replay((*path, action))
            if (key := run.key()) not in seen:
                seen.add(key)
                queue.append(((*path, action), run.actions()))
            run.discard()
    assert (len(seen), depth) == states
