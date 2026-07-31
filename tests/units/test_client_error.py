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
async def test_dispatch_missing_logs_actionable_error(
    event_namespace: EventNamespace, console_output: dict[str, list[str]]
):
    """A dispatch_function_missing error logs the substate and remediation steps.

    Args:
        event_namespace: The event namespace.
        console_output: Captured console messages.
    """
    await event_namespace.on_client_error(
        "known_sid",
        {
            "error_type": constants.ClientErrorType.DISPATCH_MISSING,
            "message": "Cannot process state update",
            "substate": "reflex___state____state.my___state____my_state",
        },
    )
    assert len(console_output["error"]) == 1
    message = console_output["error"][0]
    assert "reflex___state____state.my___state____my_state" in message
    assert "rebuild" in message.lower()


@pytest.mark.asyncio
async def test_generic_error_logs_type_and_message(
    event_namespace: EventNamespace, console_output: dict[str, list[str]]
):
    """A generic client error logs the error type and message.

    Args:
        event_namespace: The event namespace.
        console_output: Captured console messages.
    """
    await event_namespace.on_client_error(
        "known_sid",
        {
            "error_type": constants.ClientErrorType.STATE_UPDATE,
            "message": "boom",
        },
    )
    assert len(console_output["error"]) == 1
    message = console_output["error"][0]
    assert constants.ClientErrorType.STATE_UPDATE in message
    assert "boom" in message


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", ["not a dict", None, ["list"], 42])
async def test_malformed_payload_is_ignored(
    event_namespace: EventNamespace,
    console_output: dict[str, list[str]],
    payload,
):
    """Non-dict payloads are dropped without raising or logging errors.

    Args:
        event_namespace: The event namespace.
        console_output: Captured console messages.
        payload: The malformed payload to send.
    """
    await event_namespace.on_client_error("known_sid", payload)
    assert not console_output["error"]


@pytest.mark.asyncio
async def test_unknown_sid_does_not_log_error(
    event_namespace: EventNamespace, console_output: dict[str, list[str]]
):
    """Errors from sockets without a linked token do not produce error-level logs.

    Args:
        event_namespace: The event namespace.
        console_output: Captured console messages.
    """
    await event_namespace.on_client_error(
        "unknown_sid",
        {
            "error_type": constants.ClientErrorType.STATE_UPDATE,
            "message": "spam from unauthenticated socket",
        },
    )
    assert not console_output["error"]


@pytest.mark.asyncio
async def test_client_values_are_sanitized_and_truncated(
    event_namespace: EventNamespace, console_output: dict[str, list[str]]
):
    """Control characters are stripped and long messages truncated before logging.

    Args:
        event_namespace: The event namespace.
        console_output: Captured console messages.
    """
    evil = "\x1b[31mINJECT\x1b[0m\nFAKE LOG LINE\t" + "A" * 5000
    await event_namespace.on_client_error(
        "known_sid",
        {"error_type": "custom_type", "message": evil},
    )
    assert len(console_output["error"]) == 1
    message = console_output["error"][0]
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
async def test_error_level_logging_is_rate_limited_per_sid(
    event_namespace: EventNamespace, console_output: dict[str, list[str]]
):
    """A single session cannot flood the backend logs with error-level entries.

    Args:
        event_namespace: The event namespace.
        console_output: Captured console messages.
    """
    for _ in range(20):
        await event_namespace.on_client_error(
            "known_sid",
            {"error_type": "custom_type", "message": "spam"},
        )
    assert len(console_output["error"]) == EventNamespace._MAX_CLIENT_ERRORS_PER_SID
    # Disconnecting removes the counter so the mapping cannot grow unboundedly.
    task = event_namespace.on_disconnect("known_sid")
    if task is not None:
        await task
    assert "known_sid" not in event_namespace._client_error_counts


@pytest.mark.asyncio
async def test_error_logging_bounded_across_reconnects(
    event_namespace: EventNamespace, console_output: dict[str, list[str]]
):
    """Reconnecting with fresh SIDs does not grant an unlimited log budget.

    Args:
        event_namespace: The event namespace.
        console_output: Captured console messages.
    """
    for reconnect in range(50):
        sid = f"sid_{reconnect}"
        event_namespace.sid_to_token[sid] = f"token_{reconnect}"
        for _ in range(5):
            await event_namespace.on_client_error(
                sid, {"error_type": "custom_type", "message": "spam"}
            )
    assert len(console_output["error"]) == EventNamespace._MAX_CLIENT_ERRORS_PER_WINDOW
    # Once the window elapses, errors are logged again (not silenced forever).
    event_namespace._client_error_window_start -= (
        EventNamespace._CLIENT_ERROR_WINDOW_SECONDS + 1
    )
    event_namespace.sid_to_token["sid_fresh"] = "token_fresh"
    await event_namespace.on_client_error(
        "sid_fresh", {"error_type": "custom_type", "message": "after window"}
    )
    assert (
        len(console_output["error"]) == EventNamespace._MAX_CLIENT_ERRORS_PER_WINDOW + 1
    )


def test_client_error_event_name_matches_handler():
    """python-socketio dispatches events to on_<event> methods by naming
    convention; this pins the handler to SocketEvent.CLIENT_ERROR.
    """
    assert (
        f"on_{constants.SocketEvent.CLIENT_ERROR}"
        == EventNamespace.on_client_error.__name__
    )
