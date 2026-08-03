"""Unit tests for the client_error socket event handler."""

from unittest.mock import Mock

import pytest
from reflex_base.utils import console

from reflex import constants
from reflex.app import EventNamespace


@pytest.fixture
def event_namespace() -> EventNamespace:
    """An EventNamespace with a mock app and one linked client session.

    Returns:
        The event namespace.
    """
    namespace = EventNamespace(namespace="/_event", app=Mock())
    namespace.sid_to_token["known_sid"] = "some_token"
    return namespace


@pytest.fixture
def frontend_errors(event_namespace: EventNamespace) -> list[str]:
    """Capture exceptions routed to the app's frontend exception handler.

    Args:
        event_namespace: The event namespace.

    Returns:
        The captured exception messages.
    """
    errors: list[str] = []
    event_namespace.app.frontend_exception_handler = lambda exc: errors.append(str(exc))
    return errors


@pytest.fixture
def console_output(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[str]]:
    """Capture messages logged through reflex.utils.console.

    Args:
        monkeypatch: The pytest monkeypatch fixture.

    Returns:
        Captured messages keyed by log level.
    """
    captured: dict[str, list[str]] = {"error": [], "warn": [], "debug": []}
    for level in captured:
        monkeypatch.setattr(
            console,
            level,
            lambda msg, _level=level, **kwargs: captured[_level].append(msg),
        )
    return captured


@pytest.mark.asyncio
async def test_dispatch_missing_reports_actionable_error(
    event_namespace: EventNamespace, frontend_errors: list[str]
):
    """A dispatch_function_missing error reports the substate and remediation steps.

    Args:
        event_namespace: The event namespace.
        frontend_errors: Captured frontend exception handler messages.
    """
    await event_namespace.on_client_error(
        "known_sid",
        {
            "error_type": constants.ClientErrorType.DISPATCH_MISSING,
            "message": "Cannot process state update",
            "substate": "reflex___state____state.my___state____my_state",
        },
    )
    assert len(frontend_errors) == 1
    message = frontend_errors[0]
    assert "reflex___state____state.my___state____my_state" in message
    assert "rebuild" in message.lower()


@pytest.mark.asyncio
async def test_generic_error_reports_type_and_message(
    event_namespace: EventNamespace, frontend_errors: list[str]
):
    """A generic client error reports the error type and message.

    Args:
        event_namespace: The event namespace.
        frontend_errors: Captured frontend exception handler messages.
    """
    await event_namespace.on_client_error(
        "known_sid",
        {
            "error_type": constants.ClientErrorType.STATE_UPDATE,
            "message": "boom",
        },
    )
    assert len(frontend_errors) == 1
    message = frontend_errors[0]
    assert constants.ClientErrorType.STATE_UPDATE in message
    assert "boom" in message


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", ["not a dict", None, ["list"], 42])
async def test_malformed_payload_is_ignored(
    event_namespace: EventNamespace,
    frontend_errors: list[str],
    payload,
):
    """Non-dict payloads are dropped without raising or reporting errors.

    Args:
        event_namespace: The event namespace.
        frontend_errors: Captured frontend exception handler messages.
        payload: The malformed payload to send.
    """
    await event_namespace.on_client_error("known_sid", payload)
    assert not frontend_errors


@pytest.mark.asyncio
async def test_unknown_sid_does_not_report_error(
    event_namespace: EventNamespace,
    frontend_errors: list[str],
    console_output: dict[str, list[str]],
):
    """Errors from sockets without a linked token are not reported.

    Args:
        event_namespace: The event namespace.
        frontend_errors: Captured frontend exception handler messages.
        console_output: Captured console messages.
    """
    await event_namespace.on_client_error(
        "unknown_sid",
        {
            "error_type": constants.ClientErrorType.STATE_UPDATE,
            "message": "spam from unauthenticated socket",
        },
    )
    assert not frontend_errors
    assert not console_output["error"]


@pytest.mark.asyncio
async def test_client_values_are_sanitized_and_truncated(
    event_namespace: EventNamespace, frontend_errors: list[str]
):
    """Control characters are stripped and long messages truncated before reporting.

    Args:
        event_namespace: The event namespace.
        frontend_errors: Captured frontend exception handler messages.
    """
    evil = "\x1b[31mINJECT\x1b[0m\nFAKE LOG LINE\t" + "A" * 5000
    await event_namespace.on_client_error(
        "known_sid",
        {"error_type": "custom_type", "message": evil},
    )
    assert len(frontend_errors) == 1
    message = frontend_errors[0]
    assert "\x1b" not in message
    assert "\n" not in message
    assert "\t" not in message
    assert len(message) < 700


def test_sanitize_respects_max_length():
    """The sanitized value never exceeds max_length, even when truncated."""
    out = EventNamespace._sanitize_client_log_value("A" * 5000, max_length=500)
    assert len(out) <= 500
    assert out.endswith("... (truncated)")


def test_sanitized_markup_does_not_break_console():
    """Client-supplied rich markup is escaped so it cannot style backend logs
    or raise MarkupError when printed through the real console.
    """
    for payload in (
        "x[/bold]y",
        "x[/]y",
        "[blink bold red]FAKE",
        "[link=https://evil.example]z[/link]",
    ):
        sanitized = EventNamespace._sanitize_client_log_value(payload)
        # Must not raise MarkupError.
        console.error(f"[Frontend Error] {sanitized}")


@pytest.mark.asyncio
async def test_error_reporting_is_rate_limited_per_sid(
    event_namespace: EventNamespace, frontend_errors: list[str]
):
    """A single session cannot flood the backend logs with error reports.

    Args:
        event_namespace: The event namespace.
        frontend_errors: Captured frontend exception handler messages.
    """
    for _ in range(20):
        await event_namespace.on_client_error(
            "known_sid",
            {"error_type": "custom_type", "message": "spam"},
        )
    assert len(frontend_errors) == EventNamespace._MAX_CLIENT_ERRORS_PER_SID
    # Disconnecting removes the counter so the mapping cannot grow unboundedly.
    task = event_namespace.on_disconnect("known_sid")
    if task is not None:
        await task
    assert "known_sid" not in event_namespace._client_error_counts


@pytest.mark.asyncio
async def test_error_reporting_bounded_across_reconnects(
    event_namespace: EventNamespace,
    frontend_errors: list[str],
    console_output: dict[str, list[str]],
):
    """Reconnecting with fresh SIDs does not grant an unlimited report budget.

    Args:
        event_namespace: The event namespace.
        frontend_errors: Captured frontend exception handler messages.
        console_output: Captured console messages.
    """
    for reconnect in range(50):
        sid = f"sid_{reconnect}"
        event_namespace.sid_to_token[sid] = f"token_{reconnect}"
        for _ in range(5):
            await event_namespace.on_client_error(
                sid, {"error_type": "custom_type", "message": "spam"}
            )
    assert len(frontend_errors) == EventNamespace._MAX_CLIENT_ERRORS_PER_WINDOW
    # Suppression is not silent: one warning is logged when the cap trips, so
    # a flooding client cannot invisibly starve reports from other sessions.
    assert (
        len([msg for msg in console_output["warn"] if "suppressing" in msg.lower()])
        == 1
    )
    # Once the window elapses, errors are reported again (not silenced forever).
    event_namespace._client_error_window_start -= (
        EventNamespace._CLIENT_ERROR_WINDOW_SECONDS + 1
    )
    event_namespace.sid_to_token["sid_fresh"] = "token_fresh"
    await event_namespace.on_client_error(
        "sid_fresh", {"error_type": "custom_type", "message": "after window"}
    )
    assert len(frontend_errors) == EventNamespace._MAX_CLIENT_ERRORS_PER_WINDOW + 1


def test_client_error_event_name_matches_handler():
    """python-socketio dispatches events to on_<event> methods by naming
    convention; this pins the handler to SocketEvent.CLIENT_ERROR.
    """
    assert (
        f"on_{constants.SocketEvent.CLIENT_ERROR}"
        == EventNamespace.on_client_error.__name__
    )
