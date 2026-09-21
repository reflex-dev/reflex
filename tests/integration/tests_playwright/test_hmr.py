"""Integration tests for browser hot module replacement."""

import json
import time
from collections.abc import Generator
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import Page, Route, WebSocket, expect

from reflex.testing import AppHarness


def HmrApp():
    """Create an app with independently refreshable routes and a counter."""
    import reflex as rx

    class State(rx.State):
        count: int = 0
        marker: str = "hmr-context-v0"

        @rx.event
        def increment(self):
            """Increment the counter on the backend."""
            self.count += 1

    @rx.memo
    def counter() -> rx.Component:
        """Render state and event handlers in a separate module.

        Returns:
            The counter and its controls.
        """
        return rx.box(
            rx.text("hmr-ui-v0", id="hmr-version"),
            rx.text(State.count, id="count"),
            rx.text(State.marker, id="context-marker"),
            rx.button("Increment", on_click=State.increment),
            rx.button("Focus input", on_click=rx.set_focus("focus-target")),
        )

    def index():
        return rx.box(
            rx.text("index-v0", id="version"),
            rx.link("counter", href="/counter"),
        )

    def unloaded():
        return rx.text("unloaded-v0", id="unloaded-version")

    def counter_page():
        """Keep the input outside the independently refreshed counter.

        Returns:
            The input and counter.
        """
        return rx.box(rx.input(id="focus-target"), counter())

    app = rx.App()
    app.add_page(index)
    app.add_page(unloaded, route="/unloaded")
    app.add_page(counter_page, route="/counter")


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


def _find_module(directory: Path, marker: str) -> Path:
    """Locate the generated JSX module containing a marker string.

    Args:
        directory: Directory to search for generated modules.
        marker: Source text unique to one module.

    Returns:
        The module containing the marker.
    """
    matches = [path for path in directory.rglob("*.jsx") if marker in path.read_text()]
    assert len(matches) == 1, (
        f"expected one module containing {marker!r}, got {matches}"
    )
    return matches[0]


def _replace_once(path: Path, old: str, new: str) -> None:
    """Replace one occurrence in a generated module.

    Args:
        path: Generated module to edit.
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
    scan_pos = start_index
    while time.monotonic() < deadline:
        page.wait_for_timeout(100)
        while scan_pos < len(frames):
            frame = frames[scan_pos]
            scan_pos += 1
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
    index_route = _find_module(route_dir, "index-v0")
    unloaded_route = _find_module(route_dir, "unloaded-v0")
    # React Router route ids are the app-relative module path without extension.
    unloaded_route_id = f"routes/{unloaded_route.stem}"
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
    _wait_for_hmr_manifest(page, frames, unloaded_route_id, frame_index)

    _replace_once(index_route, "index-v0", "index-v1")
    expect(page.locator("#version")).to_have_text("index-v1", timeout=10_000)

    page.goto(f"{hmr_app.frontend_url.rstrip('/')}/unloaded")
    expect(page.locator("#unloaded-version")).to_have_text("unloaded-v1")


def test_route_loaded_during_held_provider_refresh_uses_mounted_provider(
    hmr_app: AppHarness, page: Page
) -> None:
    """A route loaded against a new context instance reaches the mounted provider.

    The provider module is edited and the root refresh it triggers is held, so
    the mounted provider still runs the old module instance. A route module
    loaded by navigation in that window imports the new instance. Its state,
    event dispatch, and input ref must all work, before and after the refresh.

    Args:
        hmr_app: Running application harness.
        page: Playwright page driving the application.
    """
    assert hmr_app.frontend_url is not None
    context = hmr_app.app_path / ".web" / "utils" / "context.jsx"
    original = context.read_text()
    held: list[Route] = []
    runtime_requests: list[str] = []

    def hold_root_refresh(route: Route) -> None:
        """Defer the root module's refresh so the old provider stays mounted.

        Args:
            route: Intercepted browser request.
        """
        url = urlsplit(route.request.url)
        if url.path == "/utils/state.js":
            runtime_requests.append(route.request.url)
        if url.path == "/app/root.jsx" and "t" in parse_qs(url.query):
            held.append(route)
        else:
            route.continue_()

    page.goto(hmr_app.frontend_url)
    expect(page.locator("#version")).to_be_visible()
    time_origin = page.evaluate("performance.timeOrigin")
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("**/*", hold_root_refresh)
    try:
        # The provider module self-accepts, fails refresh-boundary validation
        # because it exports data, and invalidates its importers.
        with page.expect_request(
            lambda request: (
                urlsplit(request.url).path == "/app/root.jsx"
                and "t" in parse_qs(urlsplit(request.url).query)
            )
        ):
            _replace_once(context, "hmr-context-v0", "hmr-context-v1")

        page.get_by_role("link", name="counter").click()
        expect(page.locator("#count")).to_have_text("0")
        page.get_by_role("button", name="Increment", exact=True).click()
        expect(page.locator("#count")).to_have_text("1")
        page.locator("#focus-target").fill("keep this input mounted")
        page.get_by_role("button", name="Focus input", exact=True).click()
        expect(page.locator("#focus-target")).to_be_focused()
        assert page.evaluate("performance.timeOrigin") == time_origin

        for route in held:
            route.continue_()
        held.clear()
        page.get_by_role("button", name="Increment", exact=True).click()
        expect(page.locator("#count")).to_have_text("2")
        expect(page.locator("#focus-target")).to_have_value("keep this input mounted")
        assert page.evaluate("performance.timeOrigin") == time_origin
        assert not errors
        assert not runtime_requests, "HMR reloaded the static event runtime"
    finally:
        page.close()
        context.write_text(original)
