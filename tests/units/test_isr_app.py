"""Tests for the ISR page-server app and factory helpers."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

import reflex as rx
from reflex.isr import (
    ISRManager,
    MemoryISRCache,
    RenderResult,
    create_isr_app,
    get_build_id,
    is_enabled,
)


class _Renderer:
    """Minimal renderer that echoes the path and records calls."""

    def __init__(self) -> None:
        """Initialize the call counter and rendered paths."""
        self.calls = 0
        self.paths: list[str] = []

    async def __call__(self, path: str) -> RenderResult:
        """Render the path.

        Args:
            path: The path being rendered.

        Returns:
            A render result echoing the path.
        """
        self.calls += 1
        self.paths.append(path)
        return RenderResult(html=f"<html>{path}#{self.calls}</html>", tags=("t",))


def _client(renderer: _Renderer) -> TestClient:
    """Build a test client for a page-server around ``renderer``.

    Args:
        renderer: The renderer to use.

    Returns:
        A test client for the page-server.
    """
    manager = ISRManager(
        MemoryISRCache(), renderer, build_id="b", default_revalidate=60
    )
    return TestClient(create_isr_app(manager, shell="<html>shell</html>"))


def test_serves_and_caches_rendered_html():
    """The page-server renders once and then serves from cache."""
    renderer = _Renderer()
    client = _client(renderer)

    r1 = client.get("/blog/hello")
    r2 = client.get("/blog/hello")

    for response in (r1, r2):
        assert response.status_code == 200
        assert response.content == b"<html>/blog/hello#1</html>"
        assert dict(response.headers) == {
            "content-length": "26",
            "content-type": "text/html; charset=utf-8",
        }
    assert renderer.calls == 1  # second request hit the cache


def test_renders_and_caches_the_raw_path():
    """An encoded slash reaches the renderer and cache key still encoded."""
    renderer = _Renderer()
    client = _client(renderer)

    encoded = client.get("/blog/a%2Fb")
    decoded = client.get("/blog/a/b")

    assert encoded.text == "<html>/blog/a%2Fb#1</html>"
    assert decoded.text == "<html>/blog/a/b#2</html>"
    assert client.get("/blog/a%2Fb").text == "<html>/blog/a%2Fb#1</html>"
    assert renderer.paths == ["/blog/a%2Fb", "/blog/a/b"]


def test_caches_by_path_without_query_string():
    """Requests differing only in their query string share one cached page."""
    renderer = _Renderer()
    client = _client(renderer)

    first = client.get("/search?q=a")
    second = client.get("/search?q=b")

    assert first.text == "<html>/search#1</html>"
    assert second.text == "<html>/search#1</html>"
    assert renderer.paths == ["/search"]


def test_falls_back_to_shell_on_render_failure():
    """When the renderer yields no HTML, the SPA shell is served."""

    class _NullRenderer:
        """Renderer that never produces HTML."""

        async def __call__(self, path: str) -> None:
            """Fail to render the path.

            Args:
                path: The path being rendered.
            """

    manager = ISRManager(MemoryISRCache(), _NullRenderer(), build_id="b")
    client = TestClient(create_isr_app(manager, shell="<html>SHELL</html>"))

    r = client.get("/anything")
    assert r.status_code == 200
    assert r.content == b"<html>SHELL</html>"
    assert dict(r.headers) == {
        "content-length": "18",
        "content-type": "text/html; charset=utf-8",
    }


def test_revalidate_path_endpoint(monkeypatch: pytest.MonkeyPatch):
    """POST /_isr/revalidate with a path drops that page from cache."""
    monkeypatch.setenv("REFLEX_ISR_REVALIDATE_TOKEN", "secret")
    renderer = _Renderer()
    client = _client(renderer)

    client.get("/p")
    assert renderer.calls == 1

    resp = client.post(
        "/_isr/revalidate",
        json={"path": "/p"},
        headers={"X-Reflex-ISR-Token": "secret"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"revalidated": True, "tag_pages": 0}

    assert client.get("/p").text == "<html>/p#2</html>"  # re-rendered


def test_revalidate_tag_endpoint(monkeypatch: pytest.MonkeyPatch):
    """POST /_isr/revalidate with a tag invalidates all tagged pages."""
    monkeypatch.setenv("REFLEX_ISR_REVALIDATE_TOKEN", "secret")
    renderer = _Renderer()
    client = _client(renderer)

    client.get("/a")
    client.get("/b")
    assert renderer.calls == 2

    resp = client.post(
        "/_isr/revalidate",
        json={"tag": "t"},
        headers={"X-Reflex-ISR-Token": "secret"},
    )
    assert resp.json() == {"revalidated": True, "tag_pages": 2}

    client.get("/a")
    client.get("/b")
    assert renderer.calls == 4


@pytest.mark.parametrize("headers", [{}, {"X-Reflex-ISR-Token": "wrong"}])
def test_revalidate_rejects_a_missing_or_wrong_token(
    monkeypatch: pytest.MonkeyPatch, headers: dict[str, str]
):
    """A request without the configured token leaves the cache alone.

    Args:
        monkeypatch: Sets the revalidation token.
        headers: The request headers.
    """
    monkeypatch.setenv("REFLEX_ISR_REVALIDATE_TOKEN", "secret")
    renderer = _Renderer()
    client = _client(renderer)
    client.get("/p")

    resp = client.post("/_isr/revalidate", json={"path": "/p"}, headers=headers)

    assert resp.status_code == 401
    assert resp.json() == {"error": "unauthorized"}
    assert client.get("/p").text == "<html>/p#1</html>"


def test_revalidate_disabled_without_token(monkeypatch: pytest.MonkeyPatch):
    """Without a configured token, nobody can clear the cache over HTTP."""
    monkeypatch.delenv("REFLEX_ISR_REVALIDATE_TOKEN", raising=False)
    renderer = _Renderer()
    client = _client(renderer)
    client.get("/p")

    resp = client.post("/_isr/revalidate", json={"path": "/p"})

    assert resp.status_code == 405
    assert resp.text == "Method Not Allowed"
    assert client.get("/p").text == "<html>/p#1</html>"


def test_config_helpers_reflect_isr_settings():
    """is_enabled / get_build_id read from the config."""
    off = rx.Config(app_name="t")
    assert is_enabled(off) is False

    on = rx.Config(app_name="t", isr_render_url="http://render:8000", isr_build_id="v9")
    assert is_enabled(on) is True
    assert get_build_id(on) == "v9"
