from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from reflex_sdk import (
    APIConnectionError,
    APIResponseValidationError,
    APITimeoutError,
    AsyncReflexCloud,
    InternalServerError,
    MissingTokenError,
    NotFoundError,
    RateLimitError,
)
from reflex_sdk._base import DEFAULT_TIMEOUT

from tests.units.reflex_sdk.conftest import MockAPI

TOKENS = "/api/v1/user/token"
CREATE_TOKEN = TOKENS


@pytest.fixture
async def client(mock_api: MockAPI) -> AsyncIterator[AsyncReflexCloud]:
    """A client talking to the mock API.

    Args:
        mock_api: The mock API.

    Yields:
        The client.
    """
    async with AsyncReflexCloud(
        token="test-token",
        http_client=httpx.AsyncClient(transport=mock_api.transport()),
    ) as client:
        yield client


async def test_request_decodes_response(client: AsyncReflexCloud, mock_api: MockAPI):
    mock_api.add("GET", TOKENS, httpx.Response(200, json=[]))
    assert await client._request("GET", "user/token", list) == []
    (request,) = mock_api.requests
    assert request.headers["X-API-TOKEN"] == "test-token"


async def test_request_ignores_body_without_cast(
    client: AsyncReflexCloud, mock_api: MockAPI
):
    mock_api.add("DELETE", f"{TOKENS}/ci", httpx.Response(200, text="not json"))
    assert await client._request("DELETE", "user/token/ci", None) is None


async def test_request_retries_idempotent_request(
    client: AsyncReflexCloud, mock_api: MockAPI
):
    mock_api.add(
        "GET",
        TOKENS,
        httpx.Response(503),
        httpx.Response(429, headers={"Retry-After": "0"}),
        httpx.Response(200, json=[]),
    )
    assert await client._request("GET", "user/token", list) == []
    first, second, third = mock_api.requests
    # Retries resend the same request, so the server logs one request id.
    assert first.headers["X-Request-ID"] == third.headers["X-Request-ID"]
    assert second is first


async def test_request_gives_up_after_max_retries(
    client: AsyncReflexCloud, mock_api: MockAPI
):
    mock_api.add("GET", TOKENS, httpx.Response(429))
    with pytest.raises(RateLimitError):
        await client._request("GET", "user/token", list)
    assert len(mock_api.requests) == client.max_retries + 1


async def test_request_does_not_retry_post(client: AsyncReflexCloud, mock_api: MockAPI):
    mock_api.add("POST", CREATE_TOKEN, httpx.Response(502))
    with pytest.raises(InternalServerError):
        await client._request("POST", "user/token", str, json={"name": "ci"})
    assert len(mock_api.requests) == 1


async def test_request_does_not_retry_delete(
    client: AsyncReflexCloud, mock_api: MockAPI
):
    mock_api.add("DELETE", f"{TOKENS}/ci", httpx.Response(503))
    with pytest.raises(InternalServerError):
        await client._request("DELETE", "user/token/ci", None)
    assert len(mock_api.requests) == 1


async def test_request_retries_rate_limited_post(
    client: AsyncReflexCloud, mock_api: MockAPI
):
    mock_api.add(
        "POST",
        CREATE_TOKEN,
        httpx.Response(429, headers={"Retry-After": "0"}),
        httpx.Response(200, json="token"),
    )
    assert await client._request("POST", "user/token", str, json={}) == "token"
    assert len(mock_api.requests) == 2


async def test_request_does_not_retry_client_errors(
    client: AsyncReflexCloud, mock_api: MockAPI
):
    mock_api.add("GET", TOKENS, httpx.Response(404, json={"detail": "Not Found"}))
    with pytest.raises(NotFoundError) as exc_info:
        await client._request("GET", "user/token", list)
    assert exc_info.value.detail == "Not Found"
    assert exc_info.value.request_id == mock_api.requests[0].headers["X-Request-ID"]
    assert len(mock_api.requests) == 1


async def test_request_timeout(client: AsyncReflexCloud, mock_api: MockAPI):
    def time_out(request: httpx.Request) -> httpx.Response:
        msg = "timed out"
        raise httpx.ReadTimeout(msg, request=request)

    mock_api.add("GET", TOKENS, time_out)
    with pytest.raises(APITimeoutError, match="timed out"):
        await client._request("GET", "user/token", list)
    assert len(mock_api.requests) == client.max_retries + 1


async def test_request_connection_lost(client: AsyncReflexCloud, mock_api: MockAPI):
    def drop(request: httpx.Request) -> httpx.Response:
        msg = "connection reset"
        raise httpx.ReadError(msg, request=request)

    # The server may have processed a POST whose connection broke, so it is not retried.
    mock_api.add("POST", CREATE_TOKEN, drop)
    with pytest.raises(APIConnectionError, match="connection reset") as exc_info:
        await client._request("POST", "user/token", str, json={"name": "ci"})
    assert not isinstance(exc_info.value, APITimeoutError)
    assert len(mock_api.requests) == 1


async def test_request_retries_unsent_request(
    client: AsyncReflexCloud, mock_api: MockAPI
):
    def refuse(request: httpx.Request) -> httpx.Response:
        msg = "connection refused"
        raise httpx.ConnectError(msg, request=request)

    # A request that never connected can be sent again whatever its method.
    mock_api.add("POST", CREATE_TOKEN, refuse, httpx.Response(200, json="token"))
    assert await client._request("POST", "user/token", str, json={}) == "token"
    assert len(mock_api.requests) == 2


async def test_request_gives_up_on_unsent_request(
    client: AsyncReflexCloud, mock_api: MockAPI
):
    def refuse(request: httpx.Request) -> httpx.Response:
        msg = "connection refused"
        raise httpx.ConnectError(msg, request=request)

    mock_api.add("POST", CREATE_TOKEN, refuse)
    with pytest.raises(APIConnectionError, match="connection refused"):
        await client._request("POST", "user/token", str, json={})
    assert len(mock_api.requests) == client.max_retries + 1


async def test_request_invalid_response_body(
    client: AsyncReflexCloud, mock_api: MockAPI
):
    mock_api.add("GET", TOKENS, httpx.Response(200, json={"not": "a list"}))
    with pytest.raises(APIResponseValidationError, match="expected array"):
        await client._request("GET", "user/token", list)


async def test_request_without_token(mock_api: MockAPI):
    client = AsyncReflexCloud(
        http_client=httpx.AsyncClient(transport=mock_api.transport())
    )
    with pytest.raises(MissingTokenError):
        await client._request("GET", "user/token", list)
    assert not mock_api.requests


async def test_client_closes_its_own_http_client():
    client = AsyncReflexCloud(token="test-token")
    assert client._http_client.timeout == DEFAULT_TIMEOUT
    async with client:
        pass
    assert client._http_client.is_closed


async def test_client_leaves_passed_http_client_open():
    http_client = httpx.AsyncClient()
    async with AsyncReflexCloud(token="test-token", http_client=http_client):
        pass
    assert not http_client.is_closed
    await http_client.aclose()


async def test_client_timeout(mock_api: MockAPI):
    mock_api.add("GET", TOKENS, httpx.Response(200, json=[]))
    http_client = httpx.AsyncClient(timeout=3.0, transport=mock_api.transport())
    async with AsyncReflexCloud(token="test-token", http_client=http_client) as client:
        await client._request("GET", "user/token", list)
    async with AsyncReflexCloud(
        token="test-token", http_client=http_client, timeout=7.0
    ) as client:
        await client._request("GET", "user/token", list)
    passed_client_default, explicit = mock_api.requests
    assert passed_client_default.extensions["timeout"] == httpx.Timeout(3.0).as_dict()
    assert explicit.extensions["timeout"] == httpx.Timeout(7.0).as_dict()
    await http_client.aclose()
