"""Integration tests for the backend_path config option.

Tests that backend endpoints mount at the configured prefix and that the
frontend baked with ``backend_path`` can still reach the backend for state
events, uploads, and health checks. Covers the no-prefix baseline and the
prefixed case for both dev and prod modes via ``app_harness_env``.
"""

from __future__ import annotations

import json
import time
from collections.abc import Generator
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit

import httpx
import pytest
from playwright.sync_api import Page, Route, expect
from reflex_base.config import get_config

from reflex.testing import AppHarness


def BackendPathApp():
    """App exercising state events and uploads under backend_path."""
    import reflex as rx

    class BPState(rx.State):
        counter: int = 0
        uploaded: str = ""

        @rx.event
        async def upload(self, files: list[rx.UploadFile]):
            """Read the uploaded contents into this session's state.

            Args:
                files: The uploaded files.
            """
            self.uploaded = (await files[0].read()).decode()

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
            rx.upload(id="files"),
            rx.button(
                "upload",
                on_click=BPState.upload(rx.upload_files(upload_id="files")),  # pyright: ignore [reportArgumentType]
                id="upload-btn",
            ),
            rx.text(BPState.uploaded, id="uploaded"),
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
        mp.setenv("REFLEX_SESSION_TOKEN_MODE", "enforce")
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


def test_session_exchange_does_not_block_hydration(
    backend_path_app: AppHarness, page: Page
):
    """State events run before the in-band credential exchange completes.

    Args:
        backend_path_app: The running app.
        page: The browser page.
    """
    assert backend_path_app.frontend_url is not None
    held: list[Route] = []
    page.route("**/_reflex/session", lambda route: held.append(route))
    page.goto(backend_path_app.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")
    page.click("#bump-btn")
    expect(page.locator("#counter")).to_have_text("1")
    assert held
    assert not any(
        "reflex_session_" in cookie.get("name", "") for cookie in page.context.cookies()
    )
    token = page.locator("#token").input_value()
    with page.expect_response(
        lambda response: response.url.endswith("/_reflex/session")
    ) as exchanged:
        for route in held:
            route.continue_()
    assert exchanged.value.status == 200
    cookies = [
        cookie
        for cookie in page.context.cookies()
        if "reflex_session_" in cookie.get("name", "")
    ]
    assert len(cookies) == 1
    assert cookies[0].get("httpOnly")
    assert cookies[0].get("secure")
    assert cookies[0].get("sameSite") == "None"
    assert cookies[0].get("value", "") not in page.evaluate("document.cookie")
    page.unroute("**/_reflex/session")
    page.reload()
    expect(page.locator("#token")).to_have_value(token)
    expect(page.locator("#counter")).to_have_text("1")


def test_session_tabs_and_duplicated_tab(backend_path_app: AppHarness, page: Page):
    """Tabs share one cookie while duplicated tabs receive separate state.

    Args:
        backend_path_app: The running app.
        page: The browser page.
    """
    assert backend_path_app.frontend_url is not None
    with page.expect_response(
        lambda response: response.url.endswith("/_reflex/session")
    ):
        page.goto(backend_path_app.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")
    page.click("#bump-btn")
    expect(page.locator("#counter")).to_have_text("1")
    first_token = page.locator("#token").input_value()
    stored = page.evaluate("Object.entries(sessionStorage)")
    second = page.context.new_page()
    duplicate = page.context.new_page()
    try:
        second.goto(backend_path_app.frontend_url)
        expect(second.locator("#token")).not_to_have_value("")
        duplicate.add_init_script(
            "for (const [key, value] of "
            + json.dumps(stored)
            + ") sessionStorage.setItem(key, value);"
        )
        duplicate.goto(backend_path_app.frontend_url)
        expect(duplicate.locator("#token")).not_to_have_value("")
        tokens = {
            first_token,
            second.locator("#token").input_value(),
            duplicate.locator("#token").input_value(),
        }
        assert len(tokens) == 3
        expect(duplicate.locator("#counter")).to_have_text("0")
        cookies = [
            cookie
            for cookie in page.context.cookies()
            if "reflex_session_" in cookie.get("name", "")
        ]
        assert len(cookies) == 1
        assert backend_path_app.app_instance is not None
        session = backend_path_app.app_instance._session_token_manager.decode(
            cookies[0].get("value", "")
        )
        assert session is not None
        assert all(session.authorizes(token) for token in tokens)
        second.reload()
        expect(second.locator("#token")).not_to_have_value("")
        assert second.locator("#token").input_value() in tokens
        page.reload()
        expect(page.locator("#token")).to_have_value(first_token)
        expect(page.locator("#counter")).to_have_text("1")
    finally:
        second.close()
        duplicate.close()


def test_session_upload(backend_path_app: AppHarness, page: Page):
    """A real upload carries the cookie and updates the owning session.

    Args:
        backend_path_app: The running app.
        page: The browser page.
    """
    assert backend_path_app.frontend_url is not None
    page.goto(backend_path_app.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")
    page.locator('input[type="file"]').set_input_files({
        "name": "session.txt",
        "mimeType": "text/plain",
        "buffer": b"session upload",
    })
    page.click("#upload-btn")
    expect(page.locator("#uploaded")).to_have_text("session upload")


def test_session_refresh(backend_path_app: AppHarness, page: Page):
    """An active socket renews its cookie without replacing its client token.

    Args:
        backend_path_app: The running app.
        page: The browser page.
    """
    assert backend_path_app.frontend_url is not None
    assert backend_path_app.app_instance is not None
    manager = backend_path_app.app_instance._session_token_manager
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(manager, "ttl", 10)
        mp.setattr(manager, "refresh_interval", 1)
        with page.expect_response(lambda r: r.url.endswith("/_reflex/session")):
            page.goto(backend_path_app.frontend_url)
        expect(page.locator("#token")).not_to_have_value("")
        token = page.locator("#token").input_value()
        before = next(
            c for c in page.context.cookies() if "reflex_session_" in c.get("name", "")
        )
        session = manager.decode(before.get("value", ""))
        assert session is not None
        # Wait for the configured refresh age while keeping the browser responsive.
        page.wait_for_timeout(max(0, session.issued_at + 1.1 - time.time()) * 1000)
        with page.expect_response(lambda r: r.url.endswith("/_reflex/session")):
            page.click("#bump-btn")
        expect(page.locator("#counter")).to_have_text("1")
        after = next(
            c for c in page.context.cookies() if "reflex_session_" in c.get("name", "")
        )
        renewed = manager.decode(after.get("value", ""))
        assert renewed is not None
        assert renewed.id == session.id
        assert renewed.expires_at > session.expires_at
        page.reload()
        expect(page.locator("#token")).to_have_value(token)
        expect(page.locator("#counter")).to_have_text("1")


def test_session_backend_restart(backend_path_app: AppHarness, page: Page):
    """A socket reconnects with the same cookie and client token after restart.

    Args:
        backend_path_app: The running app.
        page: The browser page.
    """
    assert backend_path_app.frontend_url is not None
    assert backend_path_app.backend is not None
    assert backend_path_app.backend_thread is not None
    with page.expect_response(lambda r: r.url.endswith("/_reflex/session")):
        page.goto(backend_path_app.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")
    token = page.locator("#token").input_value()
    page.click("#bump-btn")
    expect(page.locator("#counter")).to_have_text("1")
    port = urlsplit(get_config().api_url).port
    assert port is not None
    backend_path_app.backend.should_exit = True
    backend_path_app.backend_thread.join(timeout=10)
    assert not backend_path_app.backend_thread.is_alive()
    # The base harness supports binding the original port in both build modes.
    AppHarness._start_backend(backend_path_app, port=port)
    backend_path_app._poll_for_servers(timeout=10)
    page.click("#bump-btn")
    expect(page.locator("#counter")).to_have_text("2", timeout=15000)
    expect(page.locator("#token")).to_have_value(token)


def test_session_cross_site_iframe(
    backend_path_app: AppHarness, page: Page, tmp_path: Path
):
    """A cross-site iframe keeps its partitioned session across reloads.

    Args:
        backend_path_app: The running app.
        page: The browser page.
        tmp_path: The isolated host page directory.
    """
    assert backend_path_app.frontend_url is not None
    frontend = backend_path_app.frontend_url
    host = "127.0.0.1" if urlsplit(frontend).hostname == "localhost" else "localhost"
    (tmp_path / "index.html").write_text(
        f'<iframe src="{frontend}"></iframe>', encoding="utf-8"
    )
    # Serve a real host page so Chromium classifies both sites as loopback;
    # intercepted documents trigger unrelated local-network access restrictions.
    with ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(tmp_path))
    ) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with page.expect_response(lambda r: r.url.endswith("/_reflex/session")):
                page.goto(f"http://{host}:{server.server_port}/")
            frame = page.frame_locator("iframe")
            expect(frame.locator("#token")).not_to_have_value("")
            token = frame.locator("#token").input_value()
            frame.locator("#bump-btn").click()
            expect(frame.locator("#counter")).to_have_text("1")
            page.reload()
            expect(frame.locator("#token")).to_have_value(token)
            expect(frame.locator("#counter")).to_have_text("1")
        finally:
            server.shutdown()
            thread.join(timeout=5)
