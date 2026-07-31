"""Tests for the ISR page-server app and factory helpers."""

from __future__ import annotations

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
    """Minimal renderer that echoes the path and counts calls."""

    def __init__(self) -> None:
        """Initialize the call counter."""
        self.calls = 0

    async def __call__(self, path: str) -> RenderResult:
        """Render the path.

        Args:
            path: The path being rendered.

        Returns:
            A render result echoing the path.
        """
        self.calls += 1
        return RenderResult(html=f"<html>{path}#{self.calls}</html>", tags=("t",))


def _app(renderer: _Renderer, *, shell: str | None = "<html>shell</html>"):
    manager = ISRManager(
        MemoryISRCache(), renderer, build_id="b", default_revalidate=60
    )
    return create_isr_app(manager, shell=shell), manager


def _client(app):
    from starlette.testclient import TestClient

    return TestClient(app)


def test_serves_and_caches_rendered_html():
    """The page-server renders once and then serves from cache."""
    renderer = _Renderer()
    app, _ = _app(renderer)
    client = _client(app)

    r1 = client.get("/blog/hello")
    r2 = client.get("/blog/hello")

    assert r1.status_code == 200
    assert "/blog/hello#1" in r1.text
    assert r1.text == r2.text
    assert renderer.calls == 1  # second request hit the cache


def test_falls_back_to_shell_on_render_failure():
    """When the renderer yields no HTML, the SPA shell is served."""

    class _NullRenderer:
        async def __call__(self, path: str) -> None:
            return None

    manager = ISRManager(MemoryISRCache(), _NullRenderer(), build_id="b")
    app = create_isr_app(manager, shell="<html>SHELL</html>")
    client = _client(app)

    r = client.get("/anything")
    assert r.status_code == 200
    assert "SHELL" in r.text


def test_revalidate_path_endpoint():
    """POST /_isr/revalidate with a path drops that page from cache."""
    renderer = _Renderer()
    app, _ = _app(renderer)
    client = _client(app)

    client.get("/p")
    assert renderer.calls == 1

    resp = client.post("/_isr/revalidate", json={"path": "/p"})
    assert resp.status_code == 200
    assert resp.json()["revalidated"] is True

    client.get("/p")
    assert renderer.calls == 2  # re-rendered after invalidation


def test_revalidate_tag_endpoint():
    """POST /_isr/revalidate with a tag invalidates all tagged pages."""
    renderer = _Renderer()
    app, _ = _app(renderer)
    client = _client(app)

    client.get("/a")
    client.get("/b")
    assert renderer.calls == 2

    resp = client.post("/_isr/revalidate", json={"tag": "t"})
    assert resp.json()["tag_pages"] == 2

    client.get("/a")
    client.get("/b")
    assert renderer.calls == 4


def test_revalidate_requires_token_when_configured(monkeypatch):
    """When REFLEX_ISR_REVALIDATE_TOKEN is set, the endpoint enforces it."""
    monkeypatch.setenv("REFLEX_ISR_REVALIDATE_TOKEN", "secret")
    renderer = _Renderer()
    app, _ = _app(renderer)
    client = _client(app)

    assert client.post("/_isr/revalidate", json={"path": "/p"}).status_code == 401
    ok = client.post(
        "/_isr/revalidate",
        json={"path": "/p"},
        headers={"X-Reflex-ISR-Token": "secret"},
    )
    assert ok.status_code == 200


def test_config_helpers_reflect_isr_settings():
    """is_enabled / get_build_id read from the config."""
    off = rx.Config(app_name="t")
    assert is_enabled(off) is False

    on = rx.Config(app_name="t", isr_render_url="http://render:8000", isr_build_id="v9")
    assert is_enabled(on) is True
    assert get_build_id(on) == "v9"
