"""Unit tests for execution helpers."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from starlette.responses import FileResponse

from reflex.utils import exec as exec_utils
from reflex.utils.precompressed_staticfiles import PrecompressedStaticFiles


def _scope(
    path: str,
    accept_encoding: str | None = None,
    accept: str | None = None,
) -> dict:
    headers = []
    if accept_encoding is not None:
        headers.append((b"accept-encoding", accept_encoding.encode()))
    if accept is not None:
        headers.append((b"accept", accept.encode()))
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


@pytest.mark.asyncio
async def test_get_frontend_mount_uses_precompressed_staticfiles(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
):
    """The prod frontend mount should negotiate precompressed assets."""
    web_dir = tmp_path / ".web"
    frontend_dir = web_dir / "build" / "client" / "app"
    frontend_dir.mkdir(parents=True)
    (frontend_dir / "index.html").write_text("<html>hello</html>")
    (frontend_dir / "index.html.gz").write_bytes(b"compressed-index")

    config = SimpleNamespace(
        frontend_path="app",
        frontend_compression_formats=["gzip"],
        frontend_image_formats=["webp"],
        prepend_frontend_path=lambda path: (
            "/app" + path if path.startswith("/") else path
        ),
    )
    monkeypatch.setattr(exec_utils, "get_config", lambda: config)
    monkeypatch.setattr(exec_utils, "get_web_dir", lambda: web_dir)

    mount = exec_utils.get_frontend_mount()

    assert mount.path == "/app"
    assert isinstance(mount.app, PrecompressedStaticFiles)
    assert tuple(fmt.name for fmt in mount.app._encodings) == ("gzip",)
    assert tuple(fmt.name for fmt in mount.app._image_formats) == ("webp",)

    response = await mount.app.get_response("", _scope("/", accept_encoding="gzip"))

    assert isinstance(response, FileResponse)
    assert response.status_code == 200
    assert str(response.path).endswith("index.html.gz")
    assert response.headers["content-encoding"] == "gzip"
    assert response.headers["vary"] == "Accept-Encoding"
