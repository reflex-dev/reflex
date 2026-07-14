"""Integration tests for browser hot module replacement."""

import json
import time
from collections.abc import Generator
from pathlib import Path

import pytest
from playwright.sync_api import Page, WebSocket, expect

from reflex.testing import AppHarness


def HmrApp():
    """Create an app with a route that remains unloaded in the browser."""
    import reflex as rx

    def index():
        return rx.text("index-v0", id="version")

    def unloaded():
        return rx.text("unloaded-v0", id="unloaded-version")

    app = rx.App()
    app.add_page(index)
    app.add_page(unloaded, route="/unloaded")


@pytest.fixture(scope="module")
def hmr_app(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Run the HMR test app in development mode.

    Args:
        tmp_path_factory: Pytest temporary path factory.

    Yields:
        The running application harness.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("hmr_app"),
        app_source=HmrApp,
    ) as harness:
        yield harness


def _replace_once(path: Path, old: str, new: str) -> None:
    """Replace one occurrence in a generated route module.

    Args:
        path: Generated route module to edit.
        old: Existing source text.
        new: Replacement source text.
    """
    source = path.read_text()
    assert source.count(old) == 1
    path.write_text(source.replace(old, new))


def _wait_for_hmr_manifest(
    page: Page, frames: list[str], route_id: str, start_index: int
) -> None:
    """Wait until React Router receives a manifest update for a route.

    Args:
        page: Playwright page driving the application.
        frames: Captured Vite websocket frames.
        route_id: React Router route identifier expected in the update.
        start_index: Ignore frames captured before this index.

    Raises:
        AssertionError: If the expected update is not received.
    """
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        page.wait_for_timeout(100)
        for frame in frames[start_index:]:
            if "react-router:hmr" not in frame:
                continue
            payload = json.loads(frame)
            if payload.get("data", {}).get("route", {}).get("id") == route_id:
                return
    msg = f"no HMR manifest update received for {route_id}"
    raise AssertionError(msg)


def test_unloaded_route_update_does_not_wedge_hmr(
    hmr_app: AppHarness, page: Page
) -> None:
    """An unopened route edit must not block a later visible route update.

    Args:
        hmr_app: Running application harness.
        page: Playwright page driving the application.
    """
    assert hmr_app.frontend_url is not None
    route_dir = hmr_app.app_path / ".web" / "app" / "routes"
    index_route = route_dir / "_index.jsx"
    unloaded_route = route_dir / "[unloaded]._index.jsx"
    frames: list[str] = []

    def capture_websocket(websocket: WebSocket) -> None:
        def capture_frame(frame: bytes | str) -> None:
            frames.append(frame.decode() if isinstance(frame, bytes) else frame)

        websocket.on("framereceived", capture_frame)

    page.on("websocket", capture_websocket)
    page.goto(hmr_app.frontend_url)
    expect(page.locator("#version")).to_have_text("index-v0")

    frame_index = len(frames)
    _replace_once(unloaded_route, "unloaded-v0", "unloaded-v1")
    _wait_for_hmr_manifest(
        page,
        frames,
        "routes/[unloaded]._index",
        frame_index,
    )

    _replace_once(index_route, "index-v0", "index-v1")
    expect(page.locator("#version")).to_have_text("index-v1", timeout=10_000)

    page.goto(f"{hmr_app.frontend_url.rstrip('/')}/unloaded")
    expect(page.locator("#unloaded-version")).to_have_text("unloaded-v1")
