"""Tests for the Socket.IO event transport in reflex/socketio_namespace.py."""

import asyncio
import logging
import re
from collections.abc import AsyncGenerator
from typing import Any, cast
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
from pytest_mock import MockerFixture
from reflex_base import constants, otel
from reflex_base.registry import RegistrationContext
from reflex_base.utils import format
from socketio import ASGIApp as EngineIOApp
from socketio import AsyncServer

import reflex as rx
from reflex.app import App
from reflex.socketio_namespace import (
    EventNamespace,
    _DrainOversizedBodyMiddleware,
    _sio_dumps,
    _sio_loads,
)

from .conftest import metric_points


@pytest.fixture
def namespace(namespace_app: Mock) -> EventNamespace:
    """A namespace serving the mock app.

    Returns:
        The namespace.
    """
    return EventNamespace("/_event", namespace_app)


@pytest.mark.asyncio
async def test_connect_with_token_is_accepted(namespace: EventNamespace):
    """A client that authenticates keeps its connection and its ASGI scope."""
    scope = {"type": "websocket", "headers": []}
    accepted = await namespace.on_connect(
        "sid1", {"QUERY_STRING": "token=tok1", "asgi.scope": scope}
    )

    assert accepted is not False
    assert namespace.sid_to_token["sid1"] == "tok1"
    assert namespace._scopes["sid1"] is scope


@pytest.mark.asyncio
async def test_connect_without_token_is_refused(namespace: EventNamespace):
    """A connection that never links a token is closed, not left open.

    Nothing it sends can be served, and Socket.IO does not run the disconnect
    handler for a refused connect, so the namespace has to undo its own
    bookkeeping here.
    """
    refused = await namespace.on_connect(
        "sid1", {"QUERY_STRING": "", "asgi.scope": {"type": "websocket"}}
    )

    assert refused is False
    assert "sid1" not in namespace.sid_to_token
    assert namespace._scopes == {}


@pytest.mark.asyncio
async def test_refused_connect_is_not_counted_as_a_connection(
    namespace: EventNamespace, otel_metrics
):
    """A refused connection leaves the gauge where it was, not one above it."""
    await namespace.on_connect("sid1", {"QUERY_STRING": ""})

    (connections,) = metric_points(otel_metrics, otel.METRIC_WEBSOCKET_CONNECTIONS)
    assert connections.value == 0


@pytest.mark.asyncio
async def test_connect_processes_boot_event_from_auth(
    namespace: EventNamespace,
    namespace_app: Mock,
    linked_state: Mock,
    boot_event: dict[str, Any],
):
    """The hydrate event carried in the CONNECT packet is processed on connect.

    As the connection's first event it records the new sid and token on the
    state, so the connect does not load and save the state tree for that; a
    connect without a boot event still does.
    """
    modify_state = namespace_app.state_manager.modify_state
    environ = {
        "QUERY_STRING": "token=tok1",
        "asgi.scope": {"type": "websocket", "headers": []},
    }

    await namespace.on_connect("sid1", environ, {"event": boot_event})

    token, event = namespace_app.event_processor.enqueue.await_args.args
    assert (token, event.name) == ("tok1", "state.hydrate_and_load")
    modify_state.assert_not_called()

    # Without a boot event (or without auth at all) nothing is processed, and
    # the connect records the new sid and token on the state itself.
    namespace_app.event_processor.enqueue.reset_mock()
    await namespace.on_connect("sid2", {"QUERY_STRING": "token=tok2"}, None)
    await namespace.on_connect("sid3", {"QUERY_STRING": "token=tok3"})
    namespace_app.event_processor.enqueue.assert_not_awaited()
    assert modify_state.call_count == 2
    assert linked_state.router_data[constants.RouteVar.SESSION_ID] == "sid3"
    assert linked_state.router_data[constants.RouteVar.CLIENT_TOKEN] == "tok3"


@pytest.mark.asyncio
async def test_connect_reports_state_schema_mismatch(
    namespace: EventNamespace,
    namespace_app: Mock,
    caplog: pytest.LogCaptureFixture,
    boot_event: dict[str, Any],
):
    """A frontend compiled for another state tree is told once, and still hydrates."""
    namespace_app._state = Mock(_to_frontend_schema=Mock(return_value="backend-schema"))
    emit = namespace.emit = AsyncMock()

    def warnings() -> list[str]:
        return [
            r.getMessage()
            for r in caplog.records
            if r.name == "reflex.event_namespace" and r.levelno == logging.WARNING
        ]

    with caplog.at_level(logging.WARNING, logger="reflex.event_namespace"):
        await namespace.on_connect(
            "sid1",
            {"QUERY_STRING": "token=tok1", "asgi.scope": {"headers": []}},
            {"event": boot_event, "state_schema": "frontend-schema"},
        )

        emit.assert_awaited_once_with(
            "state_mismatch",
            {"backend": "backend-schema", "reload_cooldown_ms": 10_000},
            to="sid1",
        )
        token, event = namespace_app.event_processor.enqueue.await_args.args
        assert (token, event.name) == ("tok1", "state.hydrate_and_load")
        (message,) = warnings()
        assert "frontend-schema" in message
        assert "backend-schema" in message
        assert "sid1" in message

        # The client-supplied hash is sanitized and bounded before it is logged.
        caplog.clear()
        await namespace.on_connect(
            "sid2",
            {"QUERY_STRING": "token=tok2", "asgi.scope": {"headers": []}},
            {"event": boot_event, "state_schema": "x\nforged line [bold]" + "y" * 500},
        )

    (message,) = warnings()
    assert "forged" in message
    assert "\n" not in message
    assert "\\[bold]" in message
    assert "(truncated)" in message
    assert len(message) < 400


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "auth",
    [
        pytest.param(
            {
                "event": {"name": "state.hydrate_and_load", "payload": {}},
                "state_schema": "same",
            },
            id="matching",
        ),
        pytest.param(
            {"event": {"name": "state.hydrate_and_load", "payload": {}}},
            id="old-frontend",
        ),
        pytest.param(None, id="no-auth"),
    ],
)
async def test_connect_sends_no_mismatch_without_one(
    namespace: EventNamespace,
    namespace_app: Mock,
    linked_state: Mock,
    auth: dict[str, Any] | None,
):
    """A matching or missing frontend schema sends nothing to the client."""
    namespace_app._state._to_frontend_schema = Mock(return_value="same")
    emit = namespace.emit = AsyncMock()

    await namespace.on_connect(
        "sid1", {"QUERY_STRING": "token=tok1", "asgi.scope": {"headers": []}}, auth
    )

    emit.assert_not_awaited()
    assert namespace_app.event_processor.enqueue.await_count == (1 if auth else 0)


@pytest.mark.asyncio
async def test_connect_whose_boot_event_fails_is_refused(
    namespace: EventNamespace,
    namespace_app: Mock,
    otel_metrics,
    caplog,
    boot_event: dict[str, Any],
):
    """A boot event that fails to process refuses the connect and undoes it.

    Raising instead would leave the session registered with Socket.IO yet
    unanswered, so the client would neither hydrate nor retry.
    """
    namespace_app.event_processor.enqueue.side_effect = ValueError("bad boot event")
    environ = {
        "QUERY_STRING": "token=tok1",
        "asgi.scope": {"type": "websocket", "headers": []},
    }

    with caplog.at_level(logging.ERROR, logger="reflex.event_namespace"):
        refused = await namespace.on_connect("sid1", environ, {"event": boot_event})
    # Let the token cleanup task run.
    await asyncio.sleep(0)

    assert refused is False
    assert "Error handling the boot event" in caplog.text
    assert "sid1" not in namespace.sid_to_token
    assert "tok1" not in namespace.token_to_sid
    assert namespace._scopes == {}
    (connections,) = metric_points(otel_metrics, otel.METRIC_WEBSOCKET_CONNECTIONS)
    assert connections.value == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "data", ['{"name": "state.on_click", "payload": {}, "router_data": {}}', 42]
)
async def test_undeserializable_event_disconnects_the_session(
    namespace: EventNamespace, namespace_app: Mock, caplog, data: object
):
    """A malformed event ends the session, as on the plain transport.

    Escaping into python-socketio, the error logged a traceback per frame,
    outside any error budget, and the session stayed open.
    """
    await namespace.on_connect(
        "sid1", {"QUERY_STRING": "token=tok1", "asgi.scope": {"headers": []}}
    )
    namespace.disconnect = AsyncMock()

    with caplog.at_level(logging.DEBUG, logger="reflex.event_namespace"):
        await namespace.on_event("sid1", data)

    namespace.disconnect.assert_awaited_once_with("sid1")
    namespace_app.event_processor.enqueue.assert_not_awaited()
    assert all(record.levelno <= logging.DEBUG for record in caplog.records)


@pytest.mark.asyncio
async def test_connect_with_a_malformed_boot_event_is_refused(
    namespace: EventNamespace, namespace_app: Mock, caplog: pytest.LogCaptureFixture
):
    """A boot event that does not deserialize refuses the connect, quietly.

    Disconnecting from inside the connect handler, as a later malformed event
    does, would acknowledge a session that never hydrated. The input is
    client-controlled, so it is logged at debug level, as on the plain
    transport, rather than as a handler error with a traceback.
    """
    namespace.disconnect = AsyncMock()
    environ = {"QUERY_STRING": "token=tok1", "asgi.scope": {"headers": []}}

    with caplog.at_level(logging.DEBUG, logger="reflex.event_namespace"):
        refused = await namespace.on_connect("sid1", environ, {"event": "not an event"})
    # Let the token cleanup task run.
    await asyncio.sleep(0)

    assert refused is False
    namespace.disconnect.assert_not_awaited()
    namespace_app.event_processor.enqueue.assert_not_awaited()
    assert "tok1" not in namespace.token_to_sid
    assert all(record.levelno <= logging.DEBUG for record in caplog.records)


@pytest.mark.asyncio
@pytest.mark.parametrize("handler", ["event", "ping", "client_error"])
async def test_a_failing_handler_is_logged_within_the_error_budget(
    namespace: EventNamespace,
    namespace_app: Mock,
    caplog: pytest.LogCaptureFixture,
    handler: str,
):
    """A server-side handler failure is logged within budget and keeps the session.

    Escaping into python-socketio, it would be logged with a traceback per
    frame, outside the budget that bounds client-triggered error logs.
    """
    await namespace.on_connect(
        "sid1", {"QUERY_STRING": "token=tok1", "asgi.scope": {"headers": []}}
    )
    namespace.disconnect = AsyncMock()
    failure = RuntimeError("server bug")
    namespace_app.event_processor.enqueue.side_effect = failure
    namespace_app.frontend_exception_handler = Mock(side_effect=failure)
    namespace.emit = AsyncMock(side_effect=failure)
    calls = {
        "event": lambda: namespace.on_event(
            "sid1", {"name": "state.on_click", "payload": {}, "router_data": {}}
        ),
        "ping": lambda: namespace.on_ping("sid1"),
        "client_error": lambda: namespace.on_client_error(
            "sid1", {"error_type": "x", "message": "y"}
        ),
    }

    with caplog.at_level(logging.ERROR, logger="reflex.event_namespace"):
        for _ in range(namespace._MAX_CLIENT_ERRORS_PER_SID + 2):
            await calls[handler]()

    assert len(caplog.records) == namespace._MAX_CLIENT_ERRORS_PER_SID
    assert all("server bug" in repr(record.exc_info) for record in caplog.records)
    namespace.disconnect.assert_not_awaited()


class AuditingNamespace(EventNamespace):
    """A namespace an app customized through on_event, recording what it is handed."""

    def __init__(self, namespace: str, app: Mock):
        """Initialize the namespace."""
        super().__init__(namespace, app)
        self.seen: list[Any] = []

    async def on_event(self, sid: str, data: Any):
        """Record the event, then handle it."""
        self.seen.append(data)
        await super().on_event(sid, data)


@pytest.fixture
def auditing_namespace(namespace_app: Mock) -> AuditingNamespace:
    """A namespace overriding on_event, serving the mock app.

    Returns:
        The namespace.
    """
    return AuditingNamespace("/_event", namespace_app)


@pytest.mark.asyncio
async def test_an_on_event_override_sees_the_boot_event_of_every_connect(
    auditing_namespace: AuditingNamespace,
    namespace_app: Mock,
    boot_event: dict[str, Any],
):
    """An on_event override sees the hydrate on connect and on reconnect.

    Apps override it for authorization checks, tenant routing or auditing,
    which the boot event must not bypass.
    """
    connected = await auditing_namespace.on_connect(
        "sid1", _connect_environ("tok1"), {"event": boot_event}
    )
    cleanup = auditing_namespace.on_disconnect("sid1")
    assert cleanup is not None
    await cleanup
    reconnected = await auditing_namespace.on_connect(
        "sid2", _connect_environ("tok1"), {"event": boot_event}
    )

    assert connected is None
    assert reconnected is None
    assert auditing_namespace.seen == [boot_event, boot_event]
    assert [
        call.args[0] for call in namespace_app.event_processor.enqueue.await_args_list
    ] == ["tok1", "tok1"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("malformed", "errors"),
    [
        pytest.param(
            False, ["Error handling the boot event for session sid1."], id="raising"
        ),
        pytest.param(True, [], id="malformed"),
    ],
)
async def test_a_failing_boot_event_refuses_the_connect_under_an_on_event_override(
    auditing_namespace: AuditingNamespace,
    namespace_app: Mock,
    caplog: pytest.LogCaptureFixture,
    boot_event: dict[str, Any],
    malformed: bool,
    errors: list[str],
):
    """A boot event failing inside an on_event override still refuses the connect.

    on_event swallows a later event's failure, but acknowledged, a session
    whose boot event failed would leave the client waiting for a hydrate that
    never comes. A malformed one is refused quietly, without the disconnect a
    later malformed event gets.
    """
    boot: Any = "not an event" if malformed else boot_event
    namespace_app.event_processor.enqueue.side_effect = ValueError("bad boot event")
    auditing_namespace.disconnect = AsyncMock()

    with caplog.at_level(logging.DEBUG, logger="reflex.event_namespace"):
        refused = await auditing_namespace.on_connect(
            "sid1", _connect_environ("tok1"), {"event": boot}
        )
    # Let the token cleanup task run.
    await asyncio.sleep(0)

    assert refused is False
    assert auditing_namespace.seen == [boot]
    auditing_namespace.disconnect.assert_not_awaited()
    assert "tok1" not in auditing_namespace.token_to_sid
    assert auditing_namespace._scopes == {}
    assert [
        record.getMessage()
        for record in caplog.records
        if record.levelno > logging.DEBUG
    ] == errors


@pytest.mark.asyncio
async def test_later_events_keep_the_failure_policy_under_an_on_event_override(
    auditing_namespace: AuditingNamespace,
    namespace_app: Mock,
    caplog: pytest.LogCaptureFixture,
    boot_event: dict[str, Any],
):
    """Past the boot event, a failing event is logged and a malformed one disconnects.

    Only the boot event's failure is raised out of on_event; raised into
    python-socketio, a later one would log a traceback per frame, outside the
    session's error budget.
    """
    await auditing_namespace.on_connect(
        "sid1", _connect_environ("tok1"), {"event": boot_event}
    )
    auditing_namespace.disconnect = AsyncMock()
    namespace_app.event_processor.enqueue.side_effect = RuntimeError("server bug")

    with caplog.at_level(logging.ERROR, logger="reflex.event_namespace"):
        await auditing_namespace.on_event(
            "sid1", {"name": "state.on_click", "payload": {}, "router_data": {}}
        )
    auditing_namespace.disconnect.assert_not_awaited()
    await auditing_namespace.on_event("sid1", 42)

    assert len(auditing_namespace.seen) == 3
    assert [
        record.getMessage()
        for record in caplog.records
        if record.levelno >= logging.ERROR
    ] == ["Error handling socket event 'event' for session sid1."]
    auditing_namespace.disconnect.assert_awaited_once_with("sid1")


@pytest.mark.asyncio
async def test_a_handle_event_override_sees_every_event(
    namespace_app: Mock, boot_event: dict[str, Any]
):
    """A handle_event override sees the hydrate on connect and every later event."""
    seen: list[str] = []

    class TenantNamespace(EventNamespace):
        async def handle_event(self, sid, data, asgi_scope):
            seen.append(data["name"])
            await super().handle_event(sid, data, asgi_scope)

    namespace = TenantNamespace("/_event", namespace_app)
    await namespace.on_connect("sid1", _connect_environ("tok1"), {"event": boot_event})
    await namespace.on_event(
        "sid1", {"name": "state.on_click", "payload": {}, "router_data": {}}
    )

    assert seen == ["state.hydrate_and_load", "state.on_click"]


def test_packets_with_an_unpaired_surrogate_stay_valid_utf8():
    """A packet carrying an unpaired surrogate is escaped, as plain frames are.

    A non-UTF-8 file name decodes to one; written raw, the text frame cannot
    be encoded for sending and the update is lost.
    """
    data = _sio_dumps({"file": "bad\udcffname"}, separators=(",", ":"))

    data.encode()
    assert _sio_loads(data) == {"file": "bad\udcffname"}


@pytest.fixture
def frontend_errors(namespace: EventNamespace, namespace_app: Mock) -> list[str]:
    """Capture what a linked session's client_error reports route to the app.

    Returns:
        The reported messages.
    """
    namespace.sid_to_token["known_sid"] = "some_token"
    errors: list[str] = []
    namespace_app.frontend_exception_handler = lambda exc: errors.append(str(exc))
    return errors


def _connect_environ(token: str) -> dict[str, Any]:
    """The environ of a connecting client carrying a token and two headers.

    Args:
        token: The client token.

    Returns:
        The environ.
    """
    return {
        "QUERY_STRING": f"token={token}",
        "asgi.scope": {
            "headers": [
                (b"origin", b"http://localhost:3000"),
                (b"user-agent", b"test-agent"),
            ],
            "client": ("127.0.0.1", 1234),
        },
    }


def _client_event() -> dict[str, Any]:
    """An event as the frontend sends it.

    Returns:
        The event payload.
    """
    return {
        "name": "state.hydrate",
        "router_data": {"pathname": "/", "query": {}, "asPath": "/"},
        "payload": {},
    }


def _enqueued(namespace_app: Mock) -> list[Any]:
    """The events the namespace handed to the event processor.

    Args:
        namespace_app: The mock app.

    Returns:
        The enqueued events, in order.
    """
    return [
        call.args[1] for call in namespace_app.event_processor.enqueue.await_args_list
    ]


def test_sio_json_records_message_sizes(otel_metrics):
    """Socket.IO packet serialization records UTF-8 sizes in both directions."""
    data = _sio_dumps({"a": "é"}, separators=(",", ":"))
    assert data == '{"a":"é"}'
    assert _sio_loads(data) == {"a": "é"}
    assert _sio_loads(data.encode()) == {"a": "é"}
    # ASCII payloads take the fast path that sizes without encoding a copy.
    ascii_data = _sio_dumps({"b": "x"}, separators=(",", ":"))
    assert _sio_loads(ascii_data) == {"b": "x"}
    points = {
        p.attributes[otel.ATTR_NETWORK_IO_DIRECTION]: p.sum
        for p in metric_points(otel_metrics, otel.METRIC_WEBSOCKET_MESSAGE_SIZE)
    }
    size = len(data.encode())
    assert size == len(data) + 1
    assert points == {
        "transmit": size + len(ascii_data),
        "receive": 2 * size + len(ascii_data),
    }


@pytest.mark.asyncio
async def test_client_error_dispatch_missing_reports_actionable_error(
    namespace: EventNamespace, frontend_errors: list[str]
):
    """A dispatch_function_missing error reports the substate and the remedy."""
    await namespace.on_client_error(
        "known_sid",
        {
            "error_type": constants.ClientErrorType.DISPATCH_MISSING,
            "message": "Cannot process state update",
            "substate": "reflex___state____state.my___state____my_state",
        },
    )
    (message,) = frontend_errors
    assert "reflex___state____state.my___state____my_state" in message
    assert "skipped" in message.lower()
    assert "rebuild" in message.lower()


@pytest.mark.asyncio
async def test_client_error_generic_reports_type_and_message(
    namespace: EventNamespace, frontend_errors: list[str]
):
    """A generic client error reports the error type and message."""
    await namespace.on_client_error(
        "known_sid",
        {"error_type": constants.ClientErrorType.STATE_UPDATE, "message": "boom"},
    )
    (message,) = frontend_errors
    assert constants.ClientErrorType.STATE_UPDATE in message
    assert "boom" in message


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", ["not a dict", None, ["list"], 42])
async def test_client_error_malformed_payload_is_ignored(
    namespace: EventNamespace, frontend_errors: list[str], payload: Any
):
    """Non-dict payloads are dropped without raising or reporting errors."""
    await namespace.on_client_error("known_sid", payload)
    assert not frontend_errors


@pytest.mark.asyncio
@pytest.mark.parametrize("sid", ["known_sid", "unknown_sid"])
async def test_client_error_no_argument_emit_is_ignored(
    namespace: EventNamespace,
    frontend_errors: list[str],
    caplog: pytest.LogCaptureFixture,
    sid: str,
):
    """A payload-less client_error emit is dropped like any malformed payload.

    python-socketio dispatches ``emit("client_error")`` without a payload as
    ``on_client_error(sid)``, so a missing ``data`` argument must not raise a
    TypeError before the anti-abuse guards run.
    """
    with caplog.at_level(logging.DEBUG, logger="reflex.event_namespace"):
        await namespace.on_client_error(sid)
    assert not frontend_errors
    assert all(record.levelno <= logging.DEBUG for record in caplog.records)


@pytest.mark.asyncio
async def test_client_error_unknown_sid_does_not_report_error(
    namespace: EventNamespace,
    frontend_errors: list[str],
    caplog: pytest.LogCaptureFixture,
):
    """Errors from sockets without a linked token are not reported."""
    with caplog.at_level(logging.DEBUG, logger="reflex.event_namespace"):
        await namespace.on_client_error(
            "unknown_sid",
            {
                "error_type": constants.ClientErrorType.STATE_UPDATE,
                "message": "spam from unauthenticated socket",
            },
        )
    assert not frontend_errors
    assert all(record.levelno < logging.ERROR for record in caplog.records)


@pytest.mark.asyncio
async def test_client_error_values_are_sanitized_and_truncated(
    namespace: EventNamespace, frontend_errors: list[str]
):
    """Control characters are stripped and long messages truncated before reporting."""
    evil = "\x1b[31mINJECT\x1b[0m\nFAKE LOG LINE\t" + "A" * 5000
    await namespace.on_client_error(
        "known_sid", {"error_type": "custom_type", "message": evil}
    )
    (message,) = frontend_errors
    assert "\x1b" not in message
    assert "\n" not in message
    assert "\t" not in message
    assert len(message) < 700


@pytest.mark.asyncio
async def test_client_error_reporting_is_rate_limited_per_sid(
    namespace: EventNamespace, frontend_errors: list[str]
):
    """A single session cannot flood the backend logs with error reports."""
    for _ in range(20):
        await namespace.on_client_error(
            "known_sid", {"error_type": "custom_type", "message": "spam"}
        )
    assert len(frontend_errors) == EventNamespace._MAX_CLIENT_ERRORS_PER_SID
    # Disconnecting removes the counter so the mapping cannot grow unboundedly.
    if (task := namespace.on_disconnect("known_sid")) is not None:
        await task
    assert "known_sid" not in namespace._client_error_budget.counts


@pytest.mark.asyncio
async def test_client_error_reporting_bounded_across_reconnects(
    namespace: EventNamespace,
    frontend_errors: list[str],
    caplog: pytest.LogCaptureFixture,
):
    """Reconnecting with fresh SIDs does not grant an unlimited report budget."""
    with caplog.at_level(logging.WARNING, logger="reflex.event_namespace"):
        for reconnect in range(50):
            sid = f"sid_{reconnect}"
            namespace.sid_to_token[sid] = f"token_{reconnect}"
            for _ in range(5):
                await namespace.on_client_error(
                    sid, {"error_type": "custom_type", "message": "spam"}
                )
    assert len(frontend_errors) == EventNamespace._MAX_CLIENT_ERRORS_PER_WINDOW
    # Suppression is not silent: one warning is logged when the cap trips, so
    # a flooding client cannot invisibly starve reports from other sessions.
    assert ["suppressing" in r.getMessage() for r in caplog.records] == [True]
    # Once the window elapses, errors are reported again (not silenced forever).
    namespace._client_error_budget.window_start -= (
        EventNamespace._CLIENT_ERROR_WINDOW_SECONDS + 1
    )
    namespace.sid_to_token["sid_fresh"] = "token_fresh"
    await namespace.on_client_error(
        "sid_fresh", {"error_type": "custom_type", "message": "after window"}
    )
    assert len(frontend_errors) == EventNamespace._MAX_CLIENT_ERRORS_PER_WINDOW + 1


def test_client_error_event_name_matches_handler():
    """python-socketio dispatches events to on_<event> methods by name.

    This pins the handler to SocketEvent.CLIENT_ERROR.
    """
    assert (
        f"on_{constants.SocketEvent.CLIENT_ERROR}"
        == EventNamespace.on_client_error.__name__
    )


@pytest.mark.asyncio
async def test_on_event_uses_connection_scoped_router_data(
    token: str, namespace: EventNamespace, namespace_app: Mock
):
    """on_event merges the connection-scoped router_data into every event.

    Headers, client IP, and session id cannot change for the lifetime of a
    connection, so the decode is cached on the ASGI scope and never repeated
    per event.
    """
    environ = _connect_environ(token)
    await namespace.on_connect("sid1", environ)

    await namespace.on_event("sid1", _client_event())

    (event,) = _enqueued(namespace_app)
    assert namespace_app.event_processor.enqueue.await_args.args[0] == token
    assert event.router_data[constants.RouteVar.CLIENT_TOKEN] == token
    assert event.router_data[constants.RouteVar.SESSION_ID] == "sid1"
    assert event.router_data[constants.RouteVar.CLIENT_IP] == "127.0.0.1"
    assert event.router_data[constants.RouteVar.HEADERS] == {
        "origin": "http://localhost:3000",
        "user-agent": "test-agent",
        "asgi-scope-client": "127.0.0.1",
    }
    assert event.router_data[constants.RouteVar.PATH] == "/404"
    assert event.router_data[constants.RouteVar.QUERY] == {}

    # A later event on the same connection reuses the decoded headers.
    environ["asgi.scope"]["headers"] = [(b"origin", b"decoded-again")]
    await namespace.on_event("sid1", _client_event())
    next_event = _enqueued(namespace_app)[-1]
    assert (
        next_event.router_data[constants.RouteVar.HEADERS]["origin"]
        == "http://localhost:3000"
    )


@pytest.mark.asyncio
async def test_on_event_does_not_share_the_cached_headers(
    token: str, namespace: EventNamespace, namespace_app: Mock
):
    """Each event gets its own headers mapping, not the cached one.

    The headers reach `state.router_data`, a plain mutable dict, so sharing
    the cached mapping would let a handler mutating it corrupt the connection
    cache for every later event on the socket.
    """
    environ = _connect_environ(token)
    await namespace.on_connect("sid1", environ)

    await namespace.on_event("sid1", _client_event())
    (event,) = _enqueued(namespace_app)
    event_headers = event.router_data[constants.RouteVar.HEADERS]
    cached_headers = environ["asgi.scope"]["_reflex_static_router_data"][
        constants.RouteVar.HEADERS
    ]

    assert event_headers == cached_headers
    assert event_headers is not cached_headers
    # Mutating what the handler sees must not reach the connection cache.
    event_headers["user-agent"] = "mutated"
    assert cached_headers["user-agent"] == "test-agent"

    await namespace.on_event("sid1", _client_event())
    next_event = _enqueued(namespace_app)[-1]
    assert (
        next_event.router_data[constants.RouteVar.HEADERS]["user-agent"] == "test-agent"
    )


@pytest.mark.asyncio
async def test_on_event_builds_router_data_without_connect(
    token: str, namespace: EventNamespace, namespace_app: Mock
):
    """on_event derives the connection data from the environ if connect was missed."""
    await namespace._token_manager.link_token_to_sid(token, "sid1")
    environ = _connect_environ(token)
    namespace_app.sio = Mock(get_environ=Mock(return_value=environ))

    await namespace.on_event("sid1", _client_event())
    await namespace.on_event("sid1", _client_event())

    # The connection-scoped entries are derived once and cached on the scope.
    assert environ["asgi.scope"]["_reflex_static_router_data"] == {
        constants.RouteVar.SESSION_ID: "sid1",
        constants.RouteVar.CLIENT_IP: "127.0.0.1",
        constants.RouteVar.HEADERS: {
            "origin": "http://localhost:3000",
            "user-agent": "test-agent",
            "asgi-scope-client": "127.0.0.1",
        },
    }
    events = _enqueued(namespace_app)
    assert len(events) == 2
    for event in events:
        assert event.router_data[constants.RouteVar.SESSION_ID] == "sid1"
        assert (
            event.router_data[constants.RouteVar.HEADERS]["user-agent"] == "test-agent"
        )


@pytest_asyncio.fixture
async def app_namespace() -> AsyncGenerator[EventNamespace, None]:
    """A namespace serving a real app whose event processor is mocked.

    Yields:
        The namespace.
    """
    app = App()
    app._event_processor = Mock(enqueue=AsyncMock())
    namespace = EventNamespace("/event", app)
    yield namespace
    # The token manager is backed by redis when one is configured; drop the
    # tokens these tests link so they do not show up in another test's
    # enumeration of the shared instance.
    await namespace._token_manager.disconnect_all()


def _dropped_result_warning(label: str) -> str:
    """The full warning for a frontend event whose return value is dropped.

    Args:
        label: How the warning names the handler.

    Returns:
        The expected warning message.
    """
    return (
        f"Event handler {label} returned a value, but it was triggered from the "
        "frontend, so the value is dropped: only backend code that awaits the "
        "handler receives its return value. Return None or events to chain from "
        "a handler used as an event trigger."
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("outcome", "warns"),
    [
        (42, True),
        ({"rows": []}, True),
        (None, False),
        ([], False),
        ("raise", False),
        ("cancel", False),
    ],
)
async def test_on_event_warns_once_in_dev_when_a_frontend_result_is_dropped(
    token: str,
    clean_registration_context: RegistrationContext,
    app_namespace: EventNamespace,
    mocker: MockerFixture,
    outcome: Any,
    warns: bool,
):
    """A value returned by a handler the frontend triggered warns, once per handler.

    Only backend code awaiting a handler receives its return value. ``[]`` is
    how a handler said "no events" before return values were results, so it
    does not warn.

    Args:
        token: A token.
        clean_registration_context: Keeps the test's state out of the shared
            registration context; the app below is created inside it.
        app_namespace: The event namespace fixture.
        mocker: pytest-mock fixture.
        outcome: What the event's future resolves to, or how it ends.
        warns: Whether the dropped value is warned about.
    """

    class DroppedResultState(rx.State):
        @rx.event
        def handler(self):
            pass

    namespace = app_namespace
    assert namespace.app._registration_context is clean_registration_context
    await namespace._token_manager.link_token_to_sid(token, "sid1")
    namespace.app.sio = Mock(get_environ=Mock(return_value=_connect_environ(token)))
    warn = mocker.patch("reflex.event_namespace.logger.warning")
    loop = asyncio.get_running_loop()
    futures = [loop.create_future(), loop.create_future()]
    enqueue_mock = cast(AsyncMock, namespace.app.event_processor.enqueue)
    enqueue_mock.side_effect = futures
    payload = {
        **_client_event(),
        "name": format.format_event_handler(
            DroppedResultState.event_handlers["handler"]
        ),
    }
    for future in futures:
        await namespace.on_event("sid1", payload)
        if outcome == "raise":
            future.set_exception(ValueError("handler failed"))
        elif outcome == "cancel":
            future.cancel()
        else:
            future.set_result(outcome)
    await asyncio.sleep(0)

    if not warns:
        warn.assert_not_called()
        return
    warn.assert_called_once_with(
        _dropped_result_warning(
            "test_on_event_warns_once_in_dev_when_a_frontend_result_is_dropped"
            ".<locals>.DroppedResultState.handler"
        )
    )


@pytest.mark.asyncio
async def test_on_event_does_not_watch_frontend_results_in_prod(
    token: str,
    monkeypatch: pytest.MonkeyPatch,
):
    """In prod, a frontend event's future gets no callback: the check is dev only.

    Args:
        token: A token.
        monkeypatch: pytest monkeypatch fixture.
    """
    monkeypatch.setenv("REFLEX_ENV_MODE", constants.Env.PROD.value)
    app = App()
    future = Mock()
    app._event_processor = Mock(enqueue=AsyncMock(return_value=future))
    namespace = EventNamespace("/event", app)
    try:
        await namespace._token_manager.link_token_to_sid(token, "sid1")
        namespace.app.sio = Mock(get_environ=Mock(return_value=_connect_environ(token)))
        await namespace.on_event("sid1", _client_event())
    finally:
        await namespace._token_manager.disconnect_all()
    cast(AsyncMock, app.event_processor.enqueue).assert_awaited_once()
    future.add_done_callback.assert_not_called()


@pytest.mark.asyncio
async def test_dropped_result_warning_names_an_unregistered_event(  # noqa: RUF029
    app_namespace: EventNamespace,
    mocker: MockerFixture,
):
    """An event missing from the app's registry is named by its event name.

    Args:
        app_namespace: The event namespace fixture.
        mocker: pytest-mock fixture.
    """
    warn = mocker.patch("reflex.event_namespace.logger.warning")
    future = asyncio.get_running_loop().create_future()
    future.set_result(42)
    app_namespace._warn_dropped_result("unregistered_state.handler", future)
    warn.assert_called_once_with(_dropped_result_warning("unregistered_state.handler"))


def _polling_engine_app(max_size: int):
    """Build the socket ASGI app the way ``App._setup_state`` mounts it.

    Args:
        max_size: Value for engine.io's ``max_http_buffer_size``.

    Returns:
        A (socket.io ASGI app, engine.io server) pair for a fresh engine.io
        server.
    """
    sio = AsyncServer(
        async_mode="asgi",
        max_http_buffer_size=max_size,
        async_handlers=False,
    )
    return EngineIOApp(sio, socketio_path=""), sio.eio


async def _asgi_http_call(
    app,
    method: str,
    query_string: str,
    body: bytes = b"",
    chunk_size: int = 65536,
    path: str = "/",
):
    """Drive one HTTP request through an ASGI app with a chunked body.

    Args:
        app: The ASGI app to call.
        method: The HTTP method.
        query_string: The raw query string.
        body: The request body.
        chunk_size: Size of each http.request message body chunk.
        path: The request path.

    Returns:
        A tuple of (status, response body, request bytes consumed from receive).
    """
    chunks = [body[i : i + chunk_size] for i in range(0, len(body), chunk_size)] or [
        b""
    ]
    sent = []
    consumed = 0
    index = 0

    async def receive():  # noqa: RUF029
        """Yield the request body one chunk at a time, then disconnect.

        Returns:
            http.request messages for each chunk, then http.disconnect.
        """
        nonlocal consumed, index
        if index < len(chunks):
            chunk = chunks[index]
            index += 1
            consumed += len(chunk)
            return {
                "type": "http.request",
                "body": chunk,
                "more_body": index < len(chunks),
            }
        return {"type": "http.disconnect"}

    async def send(message):  # noqa: RUF029
        """Record an outgoing ASGI message.

        Args:
            message: The ASGI message sent by the app.
        """
        sent.append(message)

    headers = []
    if method == "POST":
        headers.append((b"content-length", str(len(body)).encode()))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": query_string.encode("latin-1"),
        "root_path": "",
        "headers": headers,
        "client": ("127.0.0.1", 12345),
        "server": ("127.0.0.1", 8000),
    }
    await app(scope, receive, send)
    status = next(m["status"] for m in sent if m["type"] == "http.response.start")
    response_body = b"".join(
        m.get("body", b"") for m in sent if m["type"] == "http.response.body"
    )
    return status, response_body, consumed


async def _polling_handshake(app, path: str = "/") -> str:
    """Open an engine.io polling session.

    Args:
        app: The ASGI app serving engine.io.
        path: The request path.

    Returns:
        The query string that addresses the new session.
    """
    status, response_body, _ = await _asgi_http_call(
        app, "GET", "EIO=4&transport=polling", path=path
    )
    assert status == 200
    sid = re.search(r'"sid":"([^"]+)"', response_body.decode())
    assert sid is not None
    return f"EIO=4&transport=polling&sid={sid.group(1)}"


async def _oversized_post(app, query_string: str, path: str = "/"):
    """POST a 1000-byte body in 100-byte chunks, failing after 10 seconds.

    Args:
        app: The ASGI app serving engine.io.
        query_string: The query string that addresses the session.
        path: The request path.

    Returns:
        A tuple of (status, response body, request bytes consumed from receive).
    """
    return await asyncio.wait_for(
        _asgi_http_call(
            app, "POST", query_string, b"x" * 1000, chunk_size=100, path=path
        ),
        timeout=10,
    )


async def test_engineio_rejects_oversized_polling_post_without_draining_body():
    """Document the engine.io behavior _DrainOversizedBodyMiddleware works around.

    engine.io rejects a polling POST larger than max_http_buffer_size with 400
    without reading the request body, stranding the client mid-send.
    """
    app, _ = _polling_engine_app(max_size=100)
    query = await _polling_handshake(app)

    # Park a poll so engine.io can deliver its CLOSE packet and answer the POST.
    poll_task = asyncio.create_task(_asgi_http_call(app, "GET", query))
    await asyncio.sleep(0.1)

    status, _, consumed = await _oversized_post(app, query)
    poll_status, _, _ = await asyncio.wait_for(poll_task, timeout=5)
    assert status == 400
    assert poll_status == 200
    assert consumed < 1000


async def test_drain_oversized_body_middleware_drains_and_rejects_oversized_post():
    """Oversized polling POST bodies are drained so the client can finish sending."""
    socket_app, eio = _polling_engine_app(max_size=100)
    app = _DrainOversizedBodyMiddleware(socket_app, eio)
    query = await _polling_handshake(app)

    # A parked poll still receives the CLOSE packet of the rejected session.
    poll_task = asyncio.create_task(_asgi_http_call(app, "GET", query))
    await asyncio.sleep(0.1)

    status, _, consumed = await _oversized_post(app, query)
    poll_status, _, _ = await asyncio.wait_for(poll_task, timeout=5)
    assert status == 400
    assert poll_status == 200
    assert consumed == 1000

    # The reconnect handshake is served normally after the rejected POST.
    await _polling_handshake(app)


async def test_drain_oversized_body_middleware_answers_post_without_parked_poll():
    """The oversized POST is answered even when no poll is in flight.

    The rejection must not wait for a poll to consume the session CLOSE packet.
    """
    socket_app, eio = _polling_engine_app(max_size=100)
    app = _DrainOversizedBodyMiddleware(socket_app, eio)
    query = await _polling_handshake(app)

    status, response_body, consumed = await _oversized_post(app, query)
    assert status == 400
    assert response_body == b'"Bad Request"'
    assert consumed == 1000

    # A later poll learns the session is gone instead of the POST hanging.
    poll_status, _, _ = await asyncio.wait_for(
        _asgi_http_call(app, "GET", query), timeout=5
    )
    assert poll_status == 400


async def test_drain_oversized_body_middleware_closes_session_for_non_utf8_query():
    """A query string that is not UTF-8 still closes the rejected session."""
    socket_app, eio = _polling_engine_app(max_size=100)
    app = _DrainOversizedBodyMiddleware(socket_app, eio)
    query = await _polling_handshake(app)

    status, _, _ = await _oversized_post(app, f"{query}&x=\xff")
    assert status == 400
    assert eio.sockets[query.rpartition("=")[2]].closed


async def test_app_event_endpoint_drains_oversized_polling_post(
    monkeypatch: pytest.MonkeyPatch, forked_registration_context: RegistrationContext
):
    """The App's event endpoint drains and answers an oversized polling POST."""
    monkeypatch.setenv("REFLEX_TRANSPORT", "polling")
    app = App(
        enable_state=False,
        sio=AsyncServer(async_mode="asgi", max_http_buffer_size=100),
    )
    app._enable_state()
    assert app._api is not None
    path = f"{constants.Endpoint.EVENT}/"
    query = await _polling_handshake(app._api, path)

    status, _, consumed = await _oversized_post(app._api, query, path)
    assert status == 400
    assert consumed == 1000


async def test_drain_oversized_body_middleware_passes_regular_requests_through():
    """Requests within the size limit reach the downstream app untouched."""
    received = []

    async def echo_app(scope, receive, send):
        """Echo app that records the first request body and replies 200.

        Args:
            scope: The ASGI connection scope.
            receive: The ASGI receive callable.
            send: The ASGI send callable.
        """
        received.append(await receive())
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    app = _DrainOversizedBodyMiddleware(echo_app, _polling_engine_app(100)[1])
    status, response_body, _ = await _asgi_http_call(app, "POST", "", b"hello")
    assert status == 200
    assert response_body == b"ok"
    assert received[0]["body"] == b"hello"

    status, _, _ = await _asgi_http_call(app, "GET", "", b"")
    assert status == 200
