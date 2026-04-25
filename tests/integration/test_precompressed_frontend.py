"""Integration tests for precompressed production frontend responses."""

from __future__ import annotations

from collections.abc import Generator
from http.client import HTTPConnection
from urllib.parse import urlsplit

import pytest

from reflex.testing import AppHarness, AppHarnessProd


def PrecompressedFrontendApp():
    """A minimal app for production static frontend checks."""
    import reflex as rx

    app = rx.App()

    @app.add_page
    def index():
        return rx.el.main(
            rx.heading("Precompressed Frontend"),
            rx.text("Hello from Reflex"),
        )


def _request_raw(
    frontend_url: str,
    path: str,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], bytes]:
    """Send a raw HTTP request without client-side decompression.

    Args:
        frontend_url: The frontend base URL.
        path: The request path.
        headers: Optional request headers.

    Returns:
        The status code, response headers, and raw response body.
    """
    parsed = urlsplit(frontend_url)
    assert parsed.hostname is not None
    assert parsed.port is not None
    connection = HTTPConnection(parsed.hostname, parsed.port, timeout=10)
    connection.request("GET", path, headers=headers or {})
    response = connection.getresponse()
    body = response.read()
    response_headers = {key.lower(): value for key, value in response.getheaders()}
    status = response.status
    connection.close()
    return status, response_headers, body


@pytest.fixture(scope="module")
def prod_test_app(
    app_harness_env: type[AppHarness],
    tmp_path_factory,
) -> Generator[AppHarness, None, None]:
    """Start the precompressed test app in production mode only.

    Yields:
        A running production app harness.
    """
    if app_harness_env is not AppHarnessProd:
        pytest.skip("precompressed frontend checks are prod-only")

    with app_harness_env.create(
        root=tmp_path_factory.mktemp("precompressed_frontend"),
        app_name="precompressed_frontend",
        app_source=PrecompressedFrontendApp,
    ) as harness:
        yield harness


def test_prod_frontend_serves_precompressed_index_html(prod_test_app: AppHarness):
    """Root HTML should be served from its precompressed sidecar."""
    assert prod_test_app.frontend_url is not None

    status, headers, body = _request_raw(
        prod_test_app.frontend_url,
        "/",
        headers={"Accept-Encoding": "gzip"},
    )

    assert status == 200
    assert headers["content-encoding"] == "gzip"
    assert headers["vary"] == "Accept-Encoding"
    assert body.startswith(b"\x1f\x8b")


def test_prod_frontend_serves_precompressed_404_fallback(prod_test_app: AppHarness):
    """Unknown routes should serve the compressed 404.html fallback."""
    assert prod_test_app.frontend_url is not None

    status, headers, body = _request_raw(
        prod_test_app.frontend_url,
        "/missing-route",
        headers={"Accept-Encoding": "gzip"},
    )

    assert status == 404
    assert headers["content-encoding"] == "gzip"
    assert body.startswith(b"\x1f\x8b")
