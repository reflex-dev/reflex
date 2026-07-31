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
