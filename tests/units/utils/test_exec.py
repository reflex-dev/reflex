"""Tests for reflex.utils.exec."""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.testclient import TestClient

from reflex.utils.exec import ReflexStaticFiles


@pytest.fixture
def static_dir(tmp_path: Path) -> Path:
    """Mimic the layout `reflex export` produces in static/.

    Args:
        tmp_path: pytest-provided temporary directory.

    Returns:
        Path to the populated static directory.
    """
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<html>index</html>")
    (static / "404.html").write_text("<html>spa shell (served as 404.html)</html>")
    (static / "__spa-fallback.html").write_text("<html>spa fallback</html>")
    about = static / "about"
    about.mkdir()
    (about / "index.html").write_text("<html>about prerendered</html>")
    (static / "about.html").write_text("<html>about prerendered</html>")
    (static / "assets").mkdir()
    (static / "assets" / "main.js").write_text("console.log(1)")
    return static


def _client(static_dir: Path, resolver=None) -> TestClient:
    app = Starlette(
        routes=[
            Mount(
                "/",
                app=ReflexStaticFiles(
                    directory=static_dir, html=True, route_resolver=resolver
                ),
                name="frontend",
            )
        ]
    )
    return TestClient(app)


def test_known_static_route_returns_200(static_dir: Path):
    client = _client(static_dir, resolver=lambda p: p if p in {"/", "/about"} else None)
    assert client.get("/about/").status_code == 200
    assert client.get("/").status_code == 200


def test_real_asset_returns_200(static_dir: Path):
    client = _client(static_dir, resolver=lambda p: None)
    assert client.get("/assets/main.js").status_code == 200


def test_dynamic_route_returns_200_with_spa_shell(static_dir: Path):
    """A path matching a dynamic route should be served as 200, not 404."""

    def resolver(path: str) -> str | None:
        return "/blog/[slug]" if path.startswith("/blog/") else None

    client = _client(static_dir, resolver=resolver)
    response = client.get("/blog/hello-world")
    assert response.status_code == 200
    assert b"spa shell" in response.content


def test_unknown_route_returns_404(static_dir: Path):
    client = _client(static_dir, resolver=lambda p: None)
    response = client.get("/this-does-not-exist")
    assert response.status_code == 404
    assert b"spa shell" in response.content


def test_missing_asset_returns_404_without_consulting_resolver(static_dir: Path):
    """Asset misses must not be rewritten to 200 even if a resolver is wired."""
    seen = []

    def resolver(path: str) -> str | None:
        seen.append(path)
        return "/anything"

    client = _client(static_dir, resolver=resolver)
    assert client.get("/assets/missing.js").status_code == 404
    assert client.get("/missing.css").status_code == 404
    assert client.get("/favicon.ico").status_code == 404
    assert seen == []


def test_no_resolver_preserves_starlette_behavior(static_dir: Path):
    client = _client(static_dir, resolver=None)
    assert client.get("/").status_code == 200
    assert client.get("/this-does-not-exist").status_code == 404


def test_html_extension_is_treated_as_navigation(static_dir: Path):
    def resolver(path: str) -> str | None:
        return "/dyn" if path.startswith("/dyn") else None

    client = _client(static_dir, resolver=resolver)
    assert client.get("/dyn/x.html").status_code == 200
    assert client.get("/missing.html").status_code == 404


def test_resolver_receives_leading_slash_path(static_dir: Path):
    seen: list[str] = []

    def resolver(path: str) -> str | None:
        seen.append(path)
        return None

    client = _client(static_dir, resolver=resolver)
    client.get("/some/nested/path")
    assert seen
    assert seen[0] == "/some/nested/path"
