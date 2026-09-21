from __future__ import annotations

import asyncio

import httpx
import pytest
from reflex_build_sdk.transports import (
    AsyncHttpxTransport,
    HttpxTransport,
    Request,
    TransportError,
)
from reflex_build_sdk.transports._base import DEFAULT_CONNECT_TIMEOUT, DEFAULT_TIMEOUT

URL = "https://build.reflex.dev/api/v1/user/token/a%2Fb?x=1"


def _request(timeout: float | None = None) -> Request:
    return Request(
        method="POST",
        url=URL,
        headers={"X-Request-ID": "abc"},
        content=b'{"a":1}',
        timeout=timeout,
    )


def _echo(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        201,
        headers={"Retry-After": "1", "X-Path": request.url.raw_path.decode()},
        json={
            "method": request.method,
            "request_id": request.headers["X-Request-ID"],
            "body": request.content.decode(),
            "timeout": request.extensions["timeout"],
        },
    )


def test_send():
    transport = HttpxTransport(httpx.Client(transport=httpx.MockTransport(_echo)))
    request = _request()
    response = transport.send(request)
    assert response.request is request
    assert response.status_code == 201
    assert response.reason_phrase == "Created"
    # Encoded path separators reach the server as sent.
    assert response.headers["x-path"] == "/api/v1/user/token/a%2Fb?x=1"
    assert response.headers["retry-after"] == "1"
    body = response.json()
    assert body["method"] == "POST"
    assert body["request_id"] == "abc"
    assert body["body"] == '{"a":1}'


def _echo_upload(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "body": request.content.decode(),
            "content_length": request.headers.get("Content-Length"),
            "transfer_encoding": request.headers.get("Transfer-Encoding"),
            "content_type": request.headers.get("Content-Type"),
        },
    )


def _upload(content: object) -> Request:
    return Request(
        method="PUT",
        url="https://storage.example.com/bucket/backend.zip?signature=x",
        headers={"Content-Length": "6"},
        content=content,  # ty:ignore[invalid-argument-type]
    )


def test_send_streamed_body():
    transport = HttpxTransport(
        httpx.Client(transport=httpx.MockTransport(_echo_upload))
    )
    response = transport.send(_upload(iter([b"abc", b"def"])))
    # The signed length is sent as is, without chunked encoding or a content type.
    assert response.json() == {
        "body": "abcdef",
        "content_length": "6",
        "transfer_encoding": None,
        "content_type": None,
    }


async def test_async_send_streamed_body():
    async def chunks():
        yield b"abc"
        # Hand control back between chunks, as reading a file would.
        await asyncio.sleep(0)
        yield b"def"

    transport = AsyncHttpxTransport(
        httpx.AsyncClient(transport=httpx.MockTransport(_echo_upload))
    )
    response = await transport.send(_upload(chunks()))
    assert response.json() == {
        "body": "abcdef",
        "content_length": "6",
        "transfer_encoding": None,
        "content_type": None,
    }
    await transport.aclose()


def test_request_timeout():
    transport = HttpxTransport(
        httpx.Client(transport=httpx.MockTransport(_echo), timeout=3.0)
    )
    assert transport.send(_request()).json()["timeout"] == httpx.Timeout(3.0).as_dict()
    assert (
        transport.send(_request(timeout=7.0)).json()["timeout"]
        == httpx.Timeout(7.0).as_dict()
    )


def test_default_client_timeout():
    transport = HttpxTransport()
    assert transport._client.timeout == httpx.Timeout(
        DEFAULT_TIMEOUT, connect=DEFAULT_CONNECT_TIMEOUT
    )
    transport.close()


@pytest.mark.parametrize(
    ("error_type", "sent", "timed_out"),
    [
        (httpx.ConnectError, False, False),
        (httpx.ConnectTimeout, False, True),
        (httpx.PoolTimeout, False, True),
        (httpx.ReadTimeout, True, True),
        (httpx.WriteTimeout, True, True),
        (httpx.ReadError, True, False),
        (httpx.RemoteProtocolError, True, False),
    ],
)
def test_errors(error_type: type[httpx.TransportError], sent: bool, timed_out: bool):
    def raise_error(request: httpx.Request) -> httpx.Response:
        msg = "boom"
        raise error_type(msg, request=request)

    transport = HttpxTransport(httpx.Client(transport=httpx.MockTransport(raise_error)))
    request = _request()
    with pytest.raises(TransportError, match="boom") as exc_info:
        transport.send(request)
    assert exc_info.value.request is request
    assert exc_info.value.sent is sent
    assert exc_info.value.timed_out is timed_out


def test_close_ownership():
    client = httpx.Client()
    HttpxTransport(client).close()
    assert not client.is_closed
    transport = HttpxTransport()
    transport.close()
    assert transport._client.is_closed


async def test_async_send():
    transport = AsyncHttpxTransport(
        httpx.AsyncClient(transport=httpx.MockTransport(_echo))
    )
    response = await transport.send(_request(timeout=7.0))
    assert response.status_code == 201
    assert response.headers["x-path"] == "/api/v1/user/token/a%2Fb?x=1"
    assert response.json()["timeout"] == httpx.Timeout(7.0).as_dict()
    await transport.aclose()


async def test_async_errors():
    def refuse(request: httpx.Request) -> httpx.Response:
        msg = "refused"
        raise httpx.ConnectError(msg, request=request)

    transport = AsyncHttpxTransport(
        httpx.AsyncClient(transport=httpx.MockTransport(refuse))
    )
    with pytest.raises(TransportError, match="refused") as exc_info:
        await transport.send(_request())
    assert exc_info.value.sent is False


async def test_async_close_ownership():
    client = httpx.AsyncClient()
    await AsyncHttpxTransport(client).aclose()
    assert not client.is_closed
    transport = AsyncHttpxTransport()
    await transport.aclose()
    assert transport._client.is_closed
    await client.aclose()
