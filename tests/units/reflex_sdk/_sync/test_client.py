# Generated from tests/units/reflex_sdk/_async/test_client.py by scripts/unasync_reflex_sdk.py. Do not edit.
from __future__ import annotations

from collections.abc import Iterator

import pytest
from reflex_sdk import (
    APIConnectionError,
    APIResponseValidationError,
    APITimeoutError,
    InternalServerError,
    MissingTokenError,
    NotFoundError,
    RateLimitError,
    ReflexCloud,
)
from reflex_sdk.transports import Request, Response, TransportError
from reflex_sdk.transports._defaults import DefaultTransport

from tests.units.reflex_sdk.conftest import MockAPI, MockTransport, reply

TOKENS = "/api/v1/user/token"


@pytest.fixture
def client(mock_api: MockAPI) -> Iterator[ReflexCloud]:
    """A client talking to the mock API.

    Args:
        mock_api: The mock API.

    Yields:
        The client.
    """
    with ReflexCloud(token="test-token", transport=MockTransport(mock_api)) as client:
        yield client


def fail(*, sent: bool, timed_out: bool = False):
    """Build a handler failing every request without a response.

    Args:
        sent: Whether the failed request may have reached the server.
        timed_out: Whether the request timed out.

    Returns:
        The handler.
    """

    def handle(request: Request) -> Response:
        msg = "timed out" if timed_out else "connection failed"
        raise TransportError(msg, request=request, sent=sent, timed_out=timed_out)

    return handle


def test_request_decodes_response(client: ReflexCloud, mock_api: MockAPI):
    mock_api.add("GET", TOKENS, reply(200, json=[]))
    assert client._request("GET", "user/token", list) == []
    (request,) = mock_api.requests
    assert request.headers["X-API-TOKEN"] == "test-token"


def test_request_ignores_body_without_cast(client: ReflexCloud, mock_api: MockAPI):
    mock_api.add("DELETE", f"{TOKENS}/ci", reply(200, text="not json"))
    assert client._request("DELETE", "user/token/ci", None) is None


def test_request_retries_idempotent_request(client: ReflexCloud, mock_api: MockAPI):
    mock_api.add(
        "GET",
        TOKENS,
        reply(503),
        reply(429, headers={"retry-after": "0"}),
        reply(200, json=[]),
    )
    assert client._request("GET", "user/token", list) == []
    first, second, third = mock_api.requests
    # Retries resend the same request, so the server logs one request id.
    assert first is second
    assert second is third


def test_request_gives_up_after_max_retries(client: ReflexCloud, mock_api: MockAPI):
    mock_api.add("GET", TOKENS, reply(429))
    with pytest.raises(RateLimitError):
        client._request("GET", "user/token", list)
    assert len(mock_api.requests) == client.max_retries + 1


def test_request_does_not_retry_post(client: ReflexCloud, mock_api: MockAPI):
    mock_api.add("POST", TOKENS, reply(502))
    with pytest.raises(InternalServerError):
        client._request("POST", "user/token", str, json={"name": "ci"})
    assert len(mock_api.requests) == 1


def test_request_does_not_retry_delete(client: ReflexCloud, mock_api: MockAPI):
    mock_api.add("DELETE", f"{TOKENS}/ci", reply(503))
    with pytest.raises(InternalServerError):
        client._request("DELETE", "user/token/ci", None)
    assert len(mock_api.requests) == 1


def test_request_retries_rate_limited_post(client: ReflexCloud, mock_api: MockAPI):
    mock_api.add(
        "POST",
        TOKENS,
        reply(429, headers={"retry-after": "0"}),
        reply(200, json="token"),
    )
    assert client._request("POST", "user/token", str, json={}) == "token"
    assert len(mock_api.requests) == 2


def test_request_does_not_retry_client_errors(client: ReflexCloud, mock_api: MockAPI):
    mock_api.add("GET", TOKENS, reply(404, json={"detail": "Not Found"}))
    with pytest.raises(NotFoundError) as exc_info:
        client._request("GET", "user/token", list)
    assert exc_info.value.detail == "Not Found"
    assert exc_info.value.request_id == mock_api.requests[0].headers["X-Request-ID"]
    assert len(mock_api.requests) == 1


def test_request_timeout(client: ReflexCloud, mock_api: MockAPI):
    mock_api.add("GET", TOKENS, fail(sent=True, timed_out=True))
    with pytest.raises(APITimeoutError, match="timed out"):
        client._request("GET", "user/token", list)
    assert len(mock_api.requests) == client.max_retries + 1


def test_request_connection_lost(client: ReflexCloud, mock_api: MockAPI):
    # The server may have processed a POST whose connection broke, so it is not retried.
    mock_api.add("POST", TOKENS, fail(sent=True))
    with pytest.raises(APIConnectionError, match="connection failed") as exc_info:
        client._request("POST", "user/token", str, json={"name": "ci"})
    assert not isinstance(exc_info.value, APITimeoutError)
    assert len(mock_api.requests) == 1


def test_request_retries_unsent_request(client: ReflexCloud, mock_api: MockAPI):
    # A request that never reached the server can be sent again whatever its method.
    mock_api.add("POST", TOKENS, fail(sent=False), reply(200, json="token"))
    assert client._request("POST", "user/token", str, json={}) == "token"
    assert len(mock_api.requests) == 2


def test_request_gives_up_on_unsent_request(client: ReflexCloud, mock_api: MockAPI):
    mock_api.add("POST", TOKENS, fail(sent=False))
    with pytest.raises(APIConnectionError, match="connection failed"):
        client._request("POST", "user/token", str, json={})
    assert len(mock_api.requests) == client.max_retries + 1


def test_request_invalid_response_body(client: ReflexCloud, mock_api: MockAPI):
    mock_api.add("GET", TOKENS, reply(200, json={"not": "a list"}))
    with pytest.raises(APIResponseValidationError, match="expected array"):
        client._request("GET", "user/token", list)


def test_request_without_token(mock_api: MockAPI):
    client = ReflexCloud(transport=MockTransport(mock_api))
    with pytest.raises(MissingTokenError):
        client._request("GET", "user/token", list)
    assert not mock_api.requests


def test_request_timeout_setting(mock_api: MockAPI):
    mock_api.add("GET", TOKENS, reply(200, json=[]))
    transport = MockTransport(mock_api)
    with ReflexCloud(token="test-token", transport=transport) as client:
        client._request("GET", "user/token", list)
    with ReflexCloud(token="test-token", transport=transport, timeout=7.0) as client:
        client._request("GET", "user/token", list)
    transport_default, explicit = mock_api.requests
    assert transport_default.timeout is None
    assert explicit.timeout == pytest.approx(7.0)


def test_client_leaves_passed_transport_open(mock_api: MockAPI):
    with ReflexCloud(transport=MockTransport(mock_api)):
        pass
    assert not mock_api.closed


def test_client_closes_its_own_transport(monkeypatch: pytest.MonkeyPatch):
    closed = []
    original_aclose = DefaultTransport.close

    def close(self: DefaultTransport) -> None:
        closed.append(self)
        original_aclose(self)

    monkeypatch.setattr(DefaultTransport, "close", close)
    with ReflexCloud() as client:
        assert type(client._transport) is DefaultTransport
    assert closed == [client._transport]
