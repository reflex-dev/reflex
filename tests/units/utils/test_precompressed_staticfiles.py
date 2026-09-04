"""Unit tests for precompressed static file serving."""

from __future__ import annotations

import asyncio
import ntpath
import os
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


def _articles_router(path: str) -> str | None:
    """Match paths belonging to the dynamic articles route.

    Args:
        path: The request path with leading slash.

    Returns:
        The articles route for paths under ``/articles/``, otherwise None.
    """
    return "articles/[id]" if path.startswith("/articles/") else None


@pytest.mark.asyncio
@pytest.mark.parametrize("encodings", [[], ["gzip"]], ids=["identity", "gzip"])
async def test_routable_spa_fallback_served_with_200(
    tmp_path: Path, encodings: list[str]
):
    """Serve the SPA fallback with 200 for paths that match the route table."""
    (tmp_path / "404.html").write_text("<html>spa-fallback</html>")

    static_files = PrecompressedStaticFiles(
        directory=tmp_path,
        html=True,
        encodings=encodings,
        router=_articles_router,
    )

    scope = _scope("/articles/7")
    response = await static_files.get_response("articles/7", scope)

    assert isinstance(response, FileResponse)
    assert response.status_code == 200
    assert str(response.path).endswith("404.html")
    assert response.media_type == "text/html"
    if encodings:
        assert response.headers["vary"] == "Accept-Encoding"
    else:
        assert "vary" not in response.headers
    assert await _collect_body(response, scope) == b"<html>spa-fallback</html>"


@pytest.mark.asyncio
async def test_routable_spa_fallback_serves_precompressed_sidecar(tmp_path: Path):
    """Serve the precompressed fallback sidecar with 200 for routable paths."""
    (tmp_path / "404.html").write_text("<html>spa-fallback</html>")
    (tmp_path / "404.html.gz").write_bytes(b"compressed-fallback")

    static_files = PrecompressedStaticFiles(
        directory=tmp_path,
        html=True,
        encodings=["gzip"],
        router=_articles_router,
    )

    scope = _scope("/articles/7", "gzip")
    response = await static_files.get_response("articles/7", scope)

    assert isinstance(response, FileResponse)
    assert response.status_code == 200
    assert str(response.path).endswith("404.html.gz")
    assert response.headers["content-encoding"] == "gzip"
    assert response.headers["vary"] == "Accept-Encoding"
    assert await _collect_body(response, scope) == b"compressed-fallback"


@pytest.mark.asyncio
@pytest.mark.parametrize("encodings", [[], ["gzip"]], ids=["identity", "gzip"])
async def test_unroutable_spa_fallback_kept_as_404(
    tmp_path: Path, encodings: list[str]
):
    """Keep serving 404 for fallback paths that match no route."""
    (tmp_path / "404.html").write_text("<html>spa-fallback</html>")

    static_files = PrecompressedStaticFiles(
        directory=tmp_path,
        html=True,
        encodings=encodings,
        router=_articles_router,
    )

    scope = _scope("/definitely-not-a-page")
    response = await static_files.get_response("definitely-not-a-page", scope)

    assert isinstance(response, FileResponse)
    assert response.status_code == 404
    assert await _collect_body(response, scope) == b"<html>spa-fallback</html>"


@pytest.mark.asyncio
async def test_missing_file_with_extension_matching_route_serves_fallback_200(
    tmp_path: Path,
):
    """A routable path is routable even when it looks like a file name."""
    (tmp_path / "404.html").write_text("<html>spa-fallback</html>")

    static_files = PrecompressedStaticFiles(
        directory=tmp_path,
        html=True,
        encodings=[],
        router=_articles_router,
    )

    response = await static_files.get_response(
        "articles/report.pdf", _scope("/articles/report.pdf")
    )

    assert isinstance(response, FileResponse)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_routable_spa_fallback_served_with_200_via_asgi(tmp_path: Path):
    """The route check survives ``StaticFiles.get_path`` normalization.

    Driving the ASGI callable (rather than ``get_response`` directly) exercises
    the OS-specific separator handling of ``get_path``, so this fails on
    Windows if the request path is matched with backslashes.
    """
    (tmp_path / "404.html").write_text("<html>spa-fallback</html>")

    static_files = PrecompressedStaticFiles(
        directory=tmp_path,
        html=True,
        encodings=[],
        router=_articles_router,
    )

    messages: list[Message] = []

    async def receive() -> dict:
        await asyncio.sleep(0)
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Message) -> None:
        await asyncio.sleep(0)
        messages.append(message)

    await static_files(_scope("/articles/7"), receive, send)

    assert messages[0]["type"] == "http.response.start"
    assert messages[0]["status"] == 200
    assert (
        b"".join(
            m.get("body", b"") for m in messages if m["type"] == "http.response.body"
        )
        == b"<html>spa-fallback</html>"
    )


@pytest.mark.asyncio
async def test_routable_spa_fallback_matches_os_separator_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Paths normalized with the Windows separator still match the route table."""
    (tmp_path / "404.html").write_text("<html>spa-fallback</html>")
    monkeypatch.setattr(os, "sep", ntpath.sep)

    static_files = PrecompressedStaticFiles(
        directory=tmp_path,
        html=True,
        encodings=[],
        router=_articles_router,
    )

    # What ``StaticFiles.get_path`` produces on Windows for ``/articles/7``.
    path = ntpath.normpath(ntpath.join("articles", "7"))
    assert path == "articles\\7"
    response = await static_files.get_response(path, _scope("/articles/7"))

    assert isinstance(response, FileResponse)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_existing_file_not_rerouted_by_router(tmp_path: Path):
    """Real files are served directly even when their path matches a route."""
    (tmp_path / "articles").mkdir()
    (tmp_path / "articles" / "7").write_text("real-file")

    static_files = PrecompressedStaticFiles(
        directory=tmp_path,
        html=True,
        encodings=[],
        router=_articles_router,
    )

    scope = _scope("/articles/7")
    response = await static_files.get_response("articles/7", scope)

    assert isinstance(response, FileResponse)
    assert response.status_code == 200
    assert str(response.path).endswith("7")
    assert await _collect_body(response, scope) == b"real-file"


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
@pytest.mark.parametrize(
    ("accept_encoding", "response_name"),
    [("identity", "app.js"), ("gzip", "app.js.gz")],
)
async def test_precompressed_static_files_use_javascript_mime_independent_of_system_mapping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    accept_encoding: str,
    response_name: str,
):
    """Serve JavaScript with its standard MIME type despite a host override."""
    (tmp_path / "app.js").write_text("console.log('hello');")
    (tmp_path / "app.js.gz").write_bytes(b"compressed-gzip")
    monkeypatch.setattr(
        "reflex.utils.precompressed_staticfiles.guess_type",
        lambda _path: ("text/plain", None),
    )

    static_files = PrecompressedStaticFiles(directory=tmp_path, encodings=["gzip"])
    response = await static_files.get_response(
        "app.js", _scope("/app.js", accept_encoding)
    )

    assert isinstance(response, FileResponse)
    assert str(response.path).endswith(response_name)
    assert response.media_type == "text/javascript"


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
