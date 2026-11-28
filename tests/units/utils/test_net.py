"""Tests for Reflex's HTTP client configuration and error handling."""

import inspect
import logging
import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx2
import pytest

from reflex.utils import net


@contextmanager
def http_server(
    name: str, requests: list[tuple[str, str, str | None]]
) -> Iterator[str]:
    """Serve a named response and record requests on a local HTTP endpoint.

    Args:
        name: The response body and request source label.
        requests: The list receiving source, target, and Host header tuples.

    Yields:
        The server's HTTP URL.
    """

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            """Record the request and return the endpoint's name."""
            requests.append((name, self.path, self.headers.get("Host")))
            body = name.encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object):
            """Suppress the server's access log.

            Args:
                format: The access-log format string.
                *args: Values interpolated into the format string.
            """

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(
            target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
        )
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}"
        finally:
            server.shutdown()
            thread.join(timeout=5)


@pytest.mark.parametrize("bypass_proxy", [False, True])
def test_http_client_routes_proxy_and_no_proxy(
    monkeypatch: pytest.MonkeyPatch, bypass_proxy: bool
):
    """HTTP_PROXY routes requests unless NO_PROXY matches the destination.

    Args:
        monkeypatch: Pytest monkeypatch fixture.
        bypass_proxy: Whether the destination bypasses the configured proxy.
    """
    for name in os.environ:
        if name.lower().endswith("_proxy"):
            monkeypatch.delenv(name)
    monkeypatch.setenv("REFLEX_HTTP_CLIENT_BIND_ADDRESS", "127.0.0.1")
    monkeypatch.setenv("SSL_NO_VERIFY", "1")
    requests: list[tuple[str, str, str | None]] = []
    with (
        http_server("origin", requests) as origin,
        http_server("proxy", requests) as proxy,
    ):
        monkeypatch.setenv("http_proxy", proxy)
        monkeypatch.setenv("no_proxy", "127.0.0.1" if bypass_proxy else "")
        url = f"{origin}/archive?version=1"
        with inspect.unwrap(net._httpx_client)() as client:
            response = net._wrap_https_func(client.get)(url, timeout=5)

        assert response.status_code == 200
        assert response.text == ("origin" if bypass_proxy else "proxy")
        assert requests == [
            (
                "origin" if bypass_proxy else "proxy",
                "/archive?version=1" if bypass_proxy else url,
                origin.removeprefix("http://"),
            )
        ]


@pytest.mark.parametrize("certificate_failure", [False, True])
def test_https_wrapper_preserves_connection_errors(
    caplog: pytest.LogCaptureFixture, certificate_failure: bool
):
    """Connection errors propagate and certificate failures include help.

    Args:
        caplog: Pytest log capture fixture.
        certificate_failure: Whether the connection failed certificate validation.
    """
    url = "https://downloads.reflex.test/archive"
    error = httpx2.ConnectError(
        "CERTIFICATE_VERIFY_FAILED" if certificate_failure else "Connection refused"
    )

    def fail(request: httpx2.Request) -> httpx2.Response:
        """Raise the selected connection error from the HTTP transport.

        Args:
            request: The outgoing request.

        Raises:
            httpx2.ConnectError: The connection failure under test.
        """
        raise error

    with (
        httpx2.Client(transport=httpx2.MockTransport(fail)) as client,
        caplog.at_level(logging.ERROR, logger=net.__name__),
        pytest.raises(httpx2.ConnectError) as caught,
    ):
        net._wrap_https_func(client.get)(url)

    assert caught.value is error
    assert caplog.messages == (
        [
            (
                f"Certificate verification failed for {url}. Set environment variable "
                "SSL_CERT_FILE to the path of the certificate file or SSL_NO_VERIFY=1 "
                "to disable verification."
            )
        ]
        if certificate_failure
        else []
    )
