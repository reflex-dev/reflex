"""Integration tests for the backend_path config option.

Tests that backend endpoints mount at the configured prefix and that the
frontend baked with ``backend_path`` can still reach the backend for state
events, uploads, and health checks. Covers the no-prefix baseline and the
prefixed case for both dev and prod modes via ``app_harness_env``.
"""

from __future__ import annotations

from collections.abc import Generator

import httpx
import pytest
from playwright.sync_api import Page, expect
from reflex_base.config import get_config

from reflex.testing import AppHarness


def BackendPathApp():
    """App exercising state events and uploads under backend_path."""
    import reflex as rx

    class BPState(rx.State):
        counter: int = 0

        @rx.event
        def bump(self):
            self.counter += 1

    upload_dir = rx.get_upload_dir()
    upload_dir.mkdir(parents=True, exist_ok=True)
    (upload_dir / "hello.txt").write_text("hello from backend_path")

    @rx.page("/")
    def index():
        return rx.box(
            rx.text(BPState.counter, id="counter"),
            rx.input(
                value=BPState.router.session.client_token,
                read_only=True,
                id="token",
            ),
            rx.button("bump", on_click=BPState.bump, id="bump-btn"),
            rx.el.a(
                "download",
                href=rx.get_upload_url("hello.txt"),
                id="upload-link",
            ),
        )

    app = rx.App()  # noqa: F841


@pytest.fixture(
    scope="module",
    params=["", "/api", "/api/v1"],
    ids=["no-prefix", "single-level", "two-level"],
)
def backend_path(request: pytest.FixtureRequest) -> str:
    """Parametrise over no-prefix and various prefix depths.

    Args:
        request: pytest fixture for accessing the current parameter.

    Returns:
        The backend_path value for this test instance.
    """
    return request.param


@pytest.fixture(scope="module")
def backend_path_app(
    app_harness_env: type[AppHarness],
    tmp_path_factory: pytest.TempPathFactory,
    backend_path: str,
) -> Generator[AppHarness, None, None]:
    """Start the BackendPathApp in dev or prod mode, with or without backend_path.

    Args:
        app_harness_env: AppHarness (dev) or AppHarnessProd (prod).
        tmp_path_factory: pytest fixture for creating temporary directories.
        backend_path: The backend_path prefix for this parametrised instance.

    Yields:
        Running AppHarness instance.
    """
    suffix = backend_path.strip("/").replace("/", "_") or "root"
    name = f"backendpath_{suffix}_{app_harness_env.__name__.lower()}"

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("REFLEX_UPLOADED_FILES_DIR", str(tmp_path_factory.mktemp("uploads")))
        if backend_path:
            mp.setenv("REFLEX_BACKEND_PATH", backend_path)
        else:
            mp.delenv("REFLEX_BACKEND_PATH", raising=False)

        with app_harness_env.create(
            root=tmp_path_factory.mktemp(name),
            app_name=name,
            app_source=BackendPathApp,
        ) as harness:
            assert harness.app_instance is not None, "app is not running"
            yield harness


def test_ping_reachable_at_prefix(backend_path_app: AppHarness, backend_path: str):
    """``/ping`` is served under backend_path (and not at the root when a prefix is set)."""
    base = get_config().api_url.rstrip("/")
    prefix = f"/{backend_path.strip('/')}" if backend_path.strip("/") else ""

    resp = httpx.get(f"{base}{prefix}/ping")
    assert resp.status_code == 200

    if prefix:
        stray = httpx.get(f"{base}/ping")
        assert stray.status_code == 404


def test_state_event_roundtrip(backend_path_app: AppHarness, page: Page):
    """Clicking a button triggers a state event through the websocket at the prefixed path."""
    assert backend_path_app.frontend_url is not None
    page.goto(backend_path_app.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")

    expect(page.locator("#counter")).to_have_text("0")
    page.click("#bump-btn")
    expect(page.locator("#counter")).to_have_text("1")
    page.click("#bump-btn")
    expect(page.locator("#counter")).to_have_text("2")


def test_uploaded_file_download(
    backend_path_app: AppHarness, backend_path: str, page: Page
):
    """``get_upload_url`` emits a URL under backend_path and the file is served from it."""
    assert backend_path_app.frontend_url is not None
    page.goto(backend_path_app.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")

    href = page.locator("#upload-link").get_attribute("href")
    assert href is not None

    prefix = f"/{backend_path.strip('/')}" if backend_path.strip("/") else ""
    if prefix:
        assert prefix in href, f"upload URL {href} missing backend_path prefix {prefix}"

    resp = httpx.get(href, follow_redirects=True)
    assert resp.status_code == 200
    assert resp.text == "hello from backend_path"
