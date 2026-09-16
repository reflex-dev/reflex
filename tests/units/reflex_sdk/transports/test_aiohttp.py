from __future__ import annotations

import asyncio
import socket
import subprocess
import sys
from collections.abc import AsyncIterator
from typing import Any

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from reflex_sdk.transports import AiohttpTransport, Request, TransportError


async def _echo(request: web.Request) -> web.Response:
    return web.json_response(
        {
            "method": request.method,
            "path": request.raw_path,
            "request_id": request.headers["X-Request-ID"],
            "body": (await request.read()).decode(),
        },
        status=201,
        headers={"Retry-After": "1"},
    )


async def _slow(request: web.Request) -> web.Response:
    await asyncio.sleep(5)
    return web.Response()


async def _redirect(request: web.Request) -> web.Response:  # noqa: RUF029
    return web.Response(status=302, headers={"Location": "/echo/redirected"})


@pytest.fixture
async def server() -> AsyncIterator[TestServer]:
    """A local HTTP server to send requests to.

    Yields:
        The running server.
    """
    app = web.Application()
    app.router.add_route("*", "/echo/{name}", _echo)
    app.router.add_get("/slow", _slow)
    app.router.add_get("/redirect", _redirect)
    server = TestServer(app)
    await server.start_server()
    yield server
    await server.close()


def _request(url: str, method: str = "GET", **kwargs: Any) -> Request:
    return Request(method=method, url=url, headers={"X-Request-ID": "abc"}, **kwargs)


async def test_send(server: TestServer):
    transport = AiohttpTransport()
    request = _request(
        str(server.make_url("/echo/a%2Fb")) + "?x=1",
        method="POST",
        content=b'{"a":1}',
    )
    response = await transport.send(request)
    await transport.aclose()
    assert response.request is request
    assert response.status_code == 201
    assert response.reason_phrase == "Created"
    assert response.headers["retry-after"] == "1"
    assert response.json() == {
        "method": "POST",
        # Encoded path separators reach the server as sent.
        "path": "/echo/a%2Fb?x=1",
        "request_id": "abc",
        "body": '{"a":1}',
    }


async def test_redirects_are_not_followed(server: TestServer):
    transport = AiohttpTransport()
    response = await transport.send(_request(str(server.make_url("/redirect"))))
    await transport.aclose()
    assert response.status_code == 302


async def test_request_timeout(server: TestServer):
    transport = AiohttpTransport()
    with pytest.raises(TransportError) as exc_info:
        await transport.send(_request(str(server.make_url("/slow")), timeout=0.05))
    await transport.aclose()
    assert exc_info.value.sent is True
    assert exc_info.value.timed_out is True


async def test_connection_refused():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    transport = AiohttpTransport()
    with pytest.raises(TransportError) as exc_info:
        await transport.send(_request(f"http://127.0.0.1:{port}/echo/x"))
    await transport.aclose()
    assert exc_info.value.sent is False
    assert exc_info.value.timed_out is False


class _FailingSession:
    """Stands in for a session whose requests raise before a response arrives."""

    def __init__(self, error: BaseException) -> None:
        self.error = error

    def request(self, *args: Any, **kwargs: Any) -> Any:
        raise self.error


@pytest.mark.parametrize(
    ("error", "sent", "timed_out"),
    [
        (aiohttp.ConnectionTimeoutError("connect"), False, True),
        (aiohttp.ServerTimeoutError("read"), True, True),
        (asyncio.TimeoutError(), True, True),
        (aiohttp.ServerDisconnectedError(), True, False),
        (aiohttp.ClientPayloadError("payload"), True, False),
    ],
)
async def test_errors(error: BaseException, sent: bool, timed_out: bool):
    transport = AiohttpTransport(_FailingSession(error))  # pyright: ignore[reportArgumentType]
    request = _request("http://127.0.0.1/echo/x")
    with pytest.raises(TransportError) as exc_info:
        await transport.send(request)
    assert exc_info.value.request is request
    assert exc_info.value.sent is sent
    assert exc_info.value.timed_out is timed_out


async def test_close_ownership(server: TestServer):
    async with aiohttp.ClientSession() as session:
        transport = AiohttpTransport(session)
        await transport.send(_request(str(server.make_url("/echo/x"))))
        await transport.aclose()
        assert not session.closed
    transport = AiohttpTransport()
    # Closing before any request has no session to close.
    await transport.aclose()
    await transport.send(_request(str(server.make_url("/echo/x"))))
    session = transport._session
    assert session is not None
    await transport.aclose()
    assert session.closed


def test_aiohttp_is_imported_on_first_use():
    code = "import sys, reflex_sdk; assert 'aiohttp' not in sys.modules"
    subprocess.run([sys.executable, "-c", code], check=True)
