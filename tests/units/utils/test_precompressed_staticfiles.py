"""Unit tests for precompressed static file serving."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from starlette.responses import FileResponse, Response
from starlette.types import Message

from reflex.utils.precompressed_staticfiles import PrecompressedStaticFiles


def _scope(path: str, accept_encoding: str | None = None) -> dict:
    headers = []
    if accept_encoding is not None:
        headers.append((b"accept-encoding", accept_encoding.encode()))
    return {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 1234),
        "server": ("testserver", 80),
        "root_path": "",
    }


async def _collect_body(response: Response, scope: dict) -> bytes:
    body = bytearray()
    unreachable = "receive should not return"

    async def receive() -> dict:
        # Block until the response cancels us; never signal a disconnect.
        await asyncio.Event().wait()
        raise AssertionError(unreachable)

    async def send(message: Message) -> None:
        await asyncio.sleep(0)
        if message["type"] == "http.response.body":
            body.extend(message.get("body", b""))

    await response(scope, receive, send)
    return bytes(body)


@pytest.mark.asyncio
async def test_precompressed_static_files_supports_html_mode(tmp_path: Path):
    """Serve a precompressed index.html sidecar for directory requests."""
    (tmp_path / "index.html").write_text("<html>hello</html>")
    (tmp_path / "index.html.gz").write_bytes(b"compressed-index")

    static_files = PrecompressedStaticFiles(
        directory=tmp_path,
        html=True,
        encodings=["gzip"],
    )

    scope = _scope("/", "gzip")
    response = await static_files.get_response("", scope)

    assert isinstance(response, FileResponse)
    assert response.status_code == 200
    assert str(response.path).endswith("index.html.gz")
    assert response.headers["content-encoding"] == "gzip"
    assert response.headers["vary"] == "Accept-Encoding"
    assert response.media_type == "text/html"
    assert await _collect_body(response, scope) == b"compressed-index"


@pytest.mark.asyncio
async def test_precompressed_static_files_supports_html_404_fallback(tmp_path: Path):
    """Serve a precompressed 404.html sidecar for HTML fallback responses."""
    (tmp_path / "404.html").write_text("<html>missing</html>")
    (tmp_path / "404.html.gz").write_bytes(b"compressed-404")

    static_files = PrecompressedStaticFiles(
        directory=tmp_path,
        html=True,
        encodings=["gzip"],
    )

    scope = _scope("/missing", "gzip")
    response = await static_files.get_response("missing", scope)

    assert isinstance(response, FileResponse)
    assert response.status_code == 404
    assert str(response.path).endswith("404.html.gz")
    assert response.headers["content-encoding"] == "gzip"
    assert response.media_type == "text/html"
    assert await _collect_body(response, scope) == b"compressed-404"


@pytest.mark.asyncio
async def test_precompressed_static_files_prefers_best_accept_encoding(
    tmp_path: Path,
):
    """Prefer the highest-quality configured encoding that exists on disk."""
    (tmp_path / "app.js").write_text("console.log('hello');")
    (tmp_path / "app.js.gz").write_bytes(b"compressed-gzip")
    (tmp_path / "app.js.br").write_bytes(b"compressed-brotli")

    static_files = PrecompressedStaticFiles(
        directory=tmp_path,
        encodings=["gzip", "brotli"],
    )

    scope = _scope("/app.js", "gzip;q=0.5, br;q=1")
    response = await static_files.get_response("app.js", scope)

    assert isinstance(response, FileResponse)
    assert str(response.path).endswith("app.js.br")
    assert response.headers["content-encoding"] == "br"
    assert response.media_type is not None
    assert "javascript" in response.media_type
    assert await _collect_body(response, scope) == b"compressed-brotli"


@pytest.mark.asyncio
async def test_precompressed_static_files_fall_back_to_identity(tmp_path: Path):
    """Keep serving the original file when no accepted sidecar is available."""
    (tmp_path / "app.js").write_text("console.log('hello');")
    (tmp_path / "app.js.gz").write_bytes(b"compressed-gzip")

    static_files = PrecompressedStaticFiles(
        directory=tmp_path,
        encodings=["gzip"],
    )

    scope = _scope("/app.js", "identity")
    response = await static_files.get_response("app.js", scope)

    assert isinstance(response, FileResponse)
    assert str(response.path).endswith("app.js")
    assert "content-encoding" not in response.headers
    assert response.headers["vary"] == "Accept-Encoding"
    assert await _collect_body(response, scope) == b"console.log('hello');"
