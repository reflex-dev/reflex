# Generated from tests/units/reflex_build_sdk/transports/test_httpx.py by packages/reflex-build-sdk/scripts/unasync.py. Do not edit.
from __future__ import annotations

import asyncio

import httpx2
import pytest
from reflex_build_sdk.transports import (
    AsyncHttpx2Transport,
    Httpx2Transport,
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


def _echo(request: httpx2.Request) -> httpx2.Response:
    return httpx2.Response(
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
    transport = Httpx2Transport(httpx2.Client(transport=httpx2.MockTransport(_echo)))
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


def _echo_upload(request: httpx2.Request) -> httpx2.Response:
    return httpx2.Response(
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
        content=content,  # pyright: ignore[reportArgumentType]
    )


def test_send_streamed_body():
    transport = Httpx2Transport(
        httpx2.Client(transport=httpx2.MockTransport(_echo_upload))
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

    transport = AsyncHttpx2Transport(
        httpx2.AsyncClient(transport=httpx2.MockTransport(_echo_upload))
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
    transport = Httpx2Transport(
        httpx2.Client(transport=httpx2.MockTransport(_echo), timeout=3.0)
    )
    assert transport.send(_request()).json()["timeout"] == httpx2.Timeout(3.0).as_dict()
    assert (
        transport.send(_request(timeout=7.0)).json()["timeout"]
        == httpx2.Timeout(7.0).as_dict()
    )


def test_default_client_timeout():
    transport = Httpx2Transport()
    assert transport._client.timeout == httpx2.Timeout(
        DEFAULT_TIMEOUT, connect=DEFAULT_CONNECT_TIMEOUT
    )
    transport.close()


@pytest.mark.parametrize(
    ("error_type", "sent", "timed_out"),
    [
        (httpx2.ConnectError, False, False),
        (httpx2.ConnectTimeout, False, True),
        (httpx2.PoolTimeout, False, True),
        (httpx2.ReadTimeout, True, True),
        (httpx2.WriteTimeout, True, True),
        (httpx2.ReadError, True, False),
        (httpx2.RemoteProtocolError, True, False),
    ],
)
def test_errors(error_type: type[httpx2.TransportError], sent: bool, timed_out: bool):
    def raise_error(request: httpx2.Request) -> httpx2.Response:
        msg = "boom"
        raise error_type(msg, request=request)

    transport = Httpx2Transport(
        httpx2.Client(transport=httpx2.MockTransport(raise_error))
    )
    request = _request()
    with pytest.raises(TransportError, match="boom") as exc_info:
        transport.send(request)
    assert exc_info.value.request is request
    assert exc_info.value.sent is sent
    assert exc_info.value.timed_out is timed_out


def test_close_ownership():
    client = httpx2.Client()
    Httpx2Transport(client).close()
    assert not client.is_closed
    transport = Httpx2Transport()
    transport.close()
    assert transport._client.is_closed


def test_keeps_falsy_client():
    class FalsyClient(httpx2.Client):
        def __bool__(self) -> bool:
            return False

    client = FalsyClient()
    transport = Httpx2Transport(client)
    assert transport._client is client
    transport.close()
    assert not client.is_closed
    client.close()


async def test_async_send():
    transport = AsyncHttpx2Transport(
        httpx2.AsyncClient(transport=httpx2.MockTransport(_echo))
    )
    response = await transport.send(_request(timeout=7.0))
    assert response.status_code == 201
    assert response.headers["x-path"] == "/api/v1/user/token/a%2Fb?x=1"
    assert response.json()["timeout"] == httpx2.Timeout(7.0).as_dict()
    await transport.aclose()


async def test_async_errors():
    def refuse(request: httpx2.Request) -> httpx2.Response:
        msg = "refused"
        raise httpx2.ConnectError(msg, request=request)

    transport = AsyncHttpx2Transport(
        httpx2.AsyncClient(transport=httpx2.MockTransport(refuse))
    )
    with pytest.raises(TransportError, match="refused") as exc_info:
        await transport.send(_request())
    assert exc_info.value.sent is False


async def test_async_close_ownership():
    client = httpx2.AsyncClient()
    await AsyncHttpx2Transport(client).aclose()
    assert not client.is_closed
    transport = AsyncHttpx2Transport()
    await transport.aclose()
    assert transport._client.is_closed
    await client.aclose()
