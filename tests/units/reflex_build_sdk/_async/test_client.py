from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from reflex_build_sdk import (
    APIConnectionError,
    APIResponseValidationError,
    APITimeoutError,
    AsyncReflexCloud,
    InternalServerError,
    MissingTokenError,
    NotFoundError,
    RateLimitError,
)
from reflex_build_sdk.transports import Request, Response, TransportError
from reflex_build_sdk.transports._defaults import AsyncDefaultTransport

from tests.units.reflex_build_sdk.conftest import AsyncMockTransport, MockAPI, reply

TOKENS = "/api/v1/user/token"


@pytest.fixture
async def client(mock_api: MockAPI) -> AsyncIterator[AsyncReflexCloud]:
    """A client talking to the mock API.

    Args:
        mock_api: The mock API.

    Yields:
        The client.
    """
    async with AsyncReflexCloud(
        token="test-token", transport=AsyncMockTransport(mock_api)
    ) as client:
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


async def test_request_decodes_response(client: AsyncReflexCloud, mock_api: MockAPI):
    mock_api.add("GET", TOKENS, reply(200, json=[]))
    assert await client._request("GET", "user/token", list) == []
    (request,) = mock_api.requests
    assert request.headers["X-API-TOKEN"] == "test-token"


async def test_request_ignores_body_without_cast(
    client: AsyncReflexCloud, mock_api: MockAPI
):
    mock_api.add("DELETE", f"{TOKENS}/ci", reply(200, text="not json"))
    assert await client._request("DELETE", "user/token/ci", None) is None


async def test_request_retries_idempotent_request(
    client: AsyncReflexCloud, mock_api: MockAPI
):
    mock_api.add(
        "GET",
        TOKENS,
        reply(503),
        reply(429, headers={"retry-after": "0"}),
        reply(200, json=[]),
    )
    assert await client._request("GET", "user/token", list) == []
    # Every attempt carries the same request id, so the server logs one request.
    assert len({request.headers["X-Request-ID"] for request in mock_api.requests}) == 1
    assert len(mock_api.requests) == 3


async def test_request_gives_up_after_max_retries(
    client: AsyncReflexCloud, mock_api: MockAPI
):
    mock_api.add("GET", TOKENS, reply(429))
    with pytest.raises(RateLimitError):
        await client._request("GET", "user/token", list)
    assert len(mock_api.requests) == client.max_retries + 1


async def test_request_does_not_retry_post(client: AsyncReflexCloud, mock_api: MockAPI):
    mock_api.add("POST", TOKENS, reply(502))
    with pytest.raises(InternalServerError):
        await client._request("POST", "user/token", str, json={"name": "ci"})
    assert len(mock_api.requests) == 1


async def test_request_does_not_retry_delete(
    client: AsyncReflexCloud, mock_api: MockAPI
):
    mock_api.add("DELETE", f"{TOKENS}/ci", reply(503))
    with pytest.raises(InternalServerError):
        await client._request("DELETE", "user/token/ci", None)
    assert len(mock_api.requests) == 1


async def test_request_retries_rate_limited_post(
    client: AsyncReflexCloud, mock_api: MockAPI
):
    mock_api.add(
        "POST",
        TOKENS,
        reply(429, headers={"retry-after": "0"}),
        reply(200, json="token"),
    )
    assert await client._request("POST", "user/token", str, json={}) == "token"
    assert len(mock_api.requests) == 2


async def test_request_does_not_retry_client_errors(
    client: AsyncReflexCloud, mock_api: MockAPI
):
    mock_api.add("GET", TOKENS, reply(404, json={"detail": "Not Found"}))
    with pytest.raises(NotFoundError) as exc_info:
        await client._request("GET", "user/token", list)
    assert exc_info.value.detail == "Not Found"
    assert exc_info.value.request_id == mock_api.requests[0].headers["X-Request-ID"]
    assert len(mock_api.requests) == 1


async def test_request_timeout(client: AsyncReflexCloud, mock_api: MockAPI):
    mock_api.add("GET", TOKENS, fail(sent=True, timed_out=True))
    with pytest.raises(APITimeoutError, match="timed out"):
        await client._request("GET", "user/token", list)
    assert len(mock_api.requests) == client.max_retries + 1


async def test_request_connection_lost(client: AsyncReflexCloud, mock_api: MockAPI):
    # The server may have processed a POST whose connection broke, so it is not retried.
    mock_api.add("POST", TOKENS, fail(sent=True))
    with pytest.raises(APIConnectionError, match="connection failed") as exc_info:
        await client._request("POST", "user/token", str, json={"name": "ci"})
    assert not isinstance(exc_info.value, APITimeoutError)
    assert len(mock_api.requests) == 1


async def test_request_retries_unsent_request(
    client: AsyncReflexCloud, mock_api: MockAPI
):
    # A request that never reached the server can be sent again whatever its method.
    mock_api.add("POST", TOKENS, fail(sent=False), reply(200, json="token"))
    assert await client._request("POST", "user/token", str, json={}) == "token"
    assert len(mock_api.requests) == 2


async def test_request_gives_up_on_unsent_request(
    client: AsyncReflexCloud, mock_api: MockAPI
):
    mock_api.add("POST", TOKENS, fail(sent=False))
    with pytest.raises(APIConnectionError, match="connection failed"):
        await client._request("POST", "user/token", str, json={})
    assert len(mock_api.requests) == client.max_retries + 1


async def test_request_invalid_response_body(
    client: AsyncReflexCloud, mock_api: MockAPI
):
    mock_api.add("GET", TOKENS, reply(200, json={"not": "a list"}))
    with pytest.raises(APIResponseValidationError, match="expected array"):
        await client._request("GET", "user/token", list)


async def test_request_without_token(mock_api: MockAPI):
    client = AsyncReflexCloud(transport=AsyncMockTransport(mock_api))
    with pytest.raises(MissingTokenError):
        await client._request("GET", "user/token", list)
    assert not mock_api.requests


async def test_request_timeout_setting(mock_api: MockAPI):
    mock_api.add("GET", TOKENS, reply(200, json=[]))
    transport = AsyncMockTransport(mock_api)
    async with AsyncReflexCloud(token="test-token", transport=transport) as client:
        await client._request("GET", "user/token", list)
    async with AsyncReflexCloud(
        token="test-token", transport=transport, timeout=7.0
    ) as client:
        await client._request("GET", "user/token", list)
    transport_default, explicit = mock_api.requests
    assert transport_default.timeout is None
    assert explicit.timeout == pytest.approx(7.0)


async def test_client_uses_falsy_transport(mock_api: MockAPI):
    class FalsyTransport(AsyncMockTransport):
        def __len__(self) -> int:
            return 0

    mock_api.add("GET", TOKENS, reply(200, json=[]))
    transport = FalsyTransport(mock_api)
    async with AsyncReflexCloud(token="test-token", transport=transport) as client:
        assert client._transport is transport
        await client._request("GET", "user/token", list)
    assert len(mock_api.requests) == 1
    assert not mock_api.closed


async def test_client_leaves_passed_transport_open(mock_api: MockAPI):
    async with AsyncReflexCloud(transport=AsyncMockTransport(mock_api)):
        pass
    assert not mock_api.closed


async def test_client_closes_its_own_transport(monkeypatch: pytest.MonkeyPatch):
    closed = []
    original_aclose = AsyncDefaultTransport.aclose

    async def aclose(self: AsyncDefaultTransport) -> None:
        closed.append(self)
        await original_aclose(self)

    monkeypatch.setattr(AsyncDefaultTransport, "aclose", aclose)
    async with AsyncReflexCloud() as client:
        assert type(client._transport) is AsyncDefaultTransport
    assert closed == [client._transport]
