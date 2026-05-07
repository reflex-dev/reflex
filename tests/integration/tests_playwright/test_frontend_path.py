"""Integration tests for the frontend_path config option.

Tests that links, redirects, assets, uploaded files, and on_load events all
work correctly when the app is served from a subpath (e.g., /prefix) and also
when served from the root (no frontend_path set).

Covers dev and prod modes via ``app_harness_env`` parametrisation.
"""

from __future__ import annotations

from collections.abc import Generator

import httpx
import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness

# ---------------------------------------------------------------------------
# Test application
# ---------------------------------------------------------------------------


def FrontendPathApp():
    """App exercising links, redirects, assets, uploads, and on_load under frontend_path."""
    from pathlib import Path

    import reflex as rx

    class FPState(rx.State):
        on_load_events: list[str] = []

        @rx.event
        def on_load_index(self):
            self.on_load_events.append("index")

        @rx.event
        def on_load_static(self):
            self.on_load_events.append("static")

        @rx.event
        def on_load_dynamic(self):
            page_id = self.page_id  # pyright: ignore[reportAttributeAccessIssue]
            self.on_load_events.append(f"dynamic-{page_id}")

        @rx.event
        def on_load_redirect_target(self):
            self.on_load_events.append("redirect-target")

        @rx.event
        def redirect_to_index(self):
            return rx.redirect("/")

        @rx.event
        def redirect_to_static(self):
            return rx.redirect("/static-page")

        @rx.event
        def redirect_to_dynamic(self):
            return rx.redirect("/dynamic/42")

    # Write a test asset into the assets directory.
    Path("assets/test_image.png").parent.mkdir(parents=True, exist_ok=True)
    # Create a tiny valid 1x1 red PNG.
    import struct
    import zlib

    def _make_png() -> bytes:
        """Create a minimal valid 1x1 red PNG image.

        Returns:
            The bytes of the PNG file.
        """

        def _chunk(chunk_type: bytes, data: bytes) -> bytes:
            c = chunk_type + data
            return (
                struct.pack(">I", len(data))
                + c
                + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
            )

        sig = b"\x89PNG\r\n\x1a\n"
        ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        raw = b"\x00\xff\x00\x00"  # filter-none + R G B
        idat = _chunk(b"IDAT", zlib.compress(raw))
        iend = _chunk(b"IEND", b"")
        return sig + ihdr + idat + iend

    Path("assets/test_image.png").write_bytes(_make_png())

    # Write an external CSS file that references the image via url().
    Path("assets/bg.css").write_text(
        ".bg-image { background-image: url(/test_image.png);"
        " width: 50px; height: 50px; }"
    )

    # Write a shared asset next to the app module so rx.asset(shared=True) can find it.
    (Path(__file__).parent / "shared_image.png").write_bytes(_make_png())

    # Write a test file to the upload directory so it's served by the backend.
    upload_dir = rx.get_upload_dir()
    upload_dir.mkdir(parents=True, exist_ok=True)
    (upload_dir / "test.txt").write_text("uploaded file content")
    (upload_dir / "test.png").write_bytes(_make_png())

    # ---- Pages ----

    @rx.page("/", on_load=FPState.on_load_index)
    def index():
        return rx.box(
            rx.text("index page", id="page-id"),
            # Client token for waiting on state hydration.
            rx.input(
                value=FPState.router.session.client_token,
                read_only=True,
                id="token",
            ),
            # Links to app-relative paths.
            rx.link("go to static", href="/static-page", id="link-static"),
            rx.link("go to dynamic 7", href="/dynamic/7", id="link-dynamic"),
            rx.link("go to dynamic 99", href="/dynamic/99", id="link-dynamic-99"),
            # Asset image using app-relative path (local asset).
            rx.el.img(src=rx.asset("test_image.png"), id="asset-img", alt="asset"),
            # Shared asset image (library-style asset next to the module file).
            rx.el.img(
                src=rx.asset("shared_image.png", shared=True),
                id="shared-asset-img",
                alt="shared asset",
            ),
            # Uploaded file via get_upload_url.
            rx.el.img(
                src=rx.get_upload_url("test.png"),
                id="upload-img",
                alt="uploaded",
            ),
            rx.link(
                "download uploaded file",
                href=rx.get_upload_url("test.txt"),
                id="upload-link",
            ),
            # Element styled by external CSS with background-image: url().
            rx.el.div(id="css-bg-image", class_name="bg-image"),
            # Buttons that trigger redirects through event handlers.
            rx.button(
                "redirect to static",
                on_click=FPState.redirect_to_static,
                id="btn-redir-static",
            ),
            rx.button(
                "redirect to dynamic 42",
                on_click=FPState.redirect_to_dynamic,
                id="btn-redir-dynamic",
            ),
            # on_load event log.
            rx.box(
                rx.foreach(FPState.on_load_events, rx.text),
                id="on-load-log",
            ),
        )

    @rx.page("/static-page", on_load=FPState.on_load_static)
    def static_page():
        return rx.box(
            rx.text("static page", id="page-id"),
            rx.input(
                value=FPState.router.session.client_token,
                read_only=True,
                id="token",
            ),
            rx.link("go home", href="/", id="link-home"),
            rx.link("go to dynamic 7", href="/dynamic/7", id="link-dynamic"),
            rx.box(
                rx.foreach(FPState.on_load_events, rx.text),
                id="on-load-log",
            ),
        )

    @rx.page("/dynamic/[page_id]", on_load=FPState.on_load_dynamic)
    def dynamic_page():
        return rx.box(
            rx.text(f"dynamic page {rx.State.page_id}", id="page-id"),  # pyright: ignore[reportAttributeAccessIssue]
            rx.input(
                value=FPState.router.session.client_token,
                read_only=True,
                id="token",
            ),
            rx.link("go home", href="/", id="link-home"),
            rx.link("go to static", href="/static-page", id="link-static"),
            rx.box(
                rx.foreach(FPState.on_load_events, rx.text),
                id="on-load-log",
            ),
        )

    # Page whose on_load redirects to a static page.
    @rx.page("/bouncer-static", on_load=rx.redirect("/static-page"))
    def bouncer_static():
        return rx.text("you should not see this")

    # Page whose on_load redirects to a dynamic page.
    @rx.page("/bouncer-dynamic", on_load=rx.redirect("/dynamic/99"))
    def bouncer_dynamic():
        return rx.text("you should not see this")

    app = rx.App(stylesheets=["bg.css"])  # noqa: F841


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(
    scope="module",
    params=["", "/prefix", "/prefix/nested"],
    ids=["no-prefix", "single-level", "two-level"],
)
def frontend_path(request: pytest.FixtureRequest) -> str:
    """Parametrise over no-prefix and various prefix depths.

    Args:
        request: pytest fixture for accessing the current parameter.

    Returns:
        The frontend_path value for this test instance.
    """
    return request.param


@pytest.fixture(scope="module")
def frontend_path_app(
    app_harness_env: type[AppHarness],
    tmp_path_factory: pytest.TempPathFactory,
    frontend_path: str,
) -> Generator[AppHarness, None, None]:
    """Start the FrontendPathApp in dev or prod mode, with or without frontend_path.

    Args:
        app_harness_env: AppHarness (dev) or AppHarnessProd (prod).
        tmp_path_factory: pytest fixture for creating temporary directories.
        frontend_path: The frontend_path prefix for this parametrised instance.

    Yields:
        Running AppHarness instance.
    """
    suffix = frontend_path.strip("/").replace("/", "_") or "root"
    name = f"frontendpath_{suffix}_{app_harness_env.__name__.lower()}"

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("REFLEX_UPLOADED_FILES_DIR", str(tmp_path_factory.mktemp("uploads")))
        if frontend_path:
            mp.setenv("REFLEX_FRONTEND_PATH", frontend_path)
        else:
            mp.delenv("REFLEX_FRONTEND_PATH", raising=False)

        with app_harness_env.create(
            root=tmp_path_factory.mktemp(name),
            app_name=name,
            app_source=FrontendPathApp,
        ) as harness:
            assert harness.app_instance is not None, "app is not running"
            yield harness


def _navigate(harness: AppHarness, page: Page, path: str = "/") -> str:
    """Navigate to ``path`` under the harness frontend and wait for hydration.

    Prepends ``frontend_url`` to *path*, navigates the Playwright *page*, and
    waits until the client token is present (indicating state hydration).

    Args:
        harness: The running AppHarness (provides ``frontend_url``).
        page: Playwright page.
        path: App-relative path to navigate to (e.g. ``/static-page``).

    Returns:
        The frontend base URL (``frontend_url`` with trailing slash stripped)
        for use in subsequent URL assertions.
    """
    base = harness.frontend_url
    assert base is not None
    base = base.rstrip("/")
    page.goto(f"{base}{path}")
    expect(page.locator("#token")).not_to_have_value("")
    return base


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_index_loads(frontend_path_app: AppHarness, page: Page):
    """Index page loads at the correct path and on_load fires."""
    _navigate(frontend_path_app, page)
    expect(page.locator("#page-id")).to_have_text("index page")
    expect(page.locator("#on-load-log")).to_contain_text("index")


def test_link_to_static_page(frontend_path_app: AppHarness, page: Page):
    """Client-side link navigates to a static route and on_load fires."""
    base = _navigate(frontend_path_app, page)

    page.click("#link-static")
    expect(page.locator("#page-id")).to_have_text("static page")
    expect(page).to_have_url(f"{base}/static-page")
    expect(page.locator("#on-load-log")).to_contain_text("static")


def test_link_to_dynamic_page(frontend_path_app: AppHarness, page: Page):
    """Client-side link navigates to a dynamic route and on_load fires."""
    base = _navigate(frontend_path_app, page)

    page.click("#link-dynamic")
    expect(page.locator("#page-id")).to_contain_text("dynamic page")
    expect(page).to_have_url(f"{base}/dynamic/7")
    expect(page.locator("#on-load-log")).to_contain_text("dynamic-7")


def test_direct_navigation_static(frontend_path_app: AppHarness, page: Page):
    """Direct URL navigation to a static page works (full page load)."""
    _navigate(frontend_path_app, page, "/static-page")
    expect(page.locator("#page-id")).to_have_text("static page")
    expect(page.locator("#on-load-log")).to_contain_text("static")


def test_direct_navigation_dynamic(frontend_path_app: AppHarness, page: Page):
    """Direct URL navigation to a dynamic page works (full page load)."""
    _navigate(frontend_path_app, page, "/dynamic/42")
    expect(page.locator("#page-id")).to_contain_text("dynamic page")
    expect(page.locator("#on-load-log")).to_contain_text("dynamic-42")


def test_redirect_to_static(frontend_path_app: AppHarness, page: Page):
    """Event handler redirect to a static route works."""
    base = _navigate(frontend_path_app, page)

    page.click("#btn-redir-static")
    expect(page.locator("#page-id")).to_have_text("static page")
    expect(page).to_have_url(f"{base}/static-page")


def test_redirect_to_dynamic(frontend_path_app: AppHarness, page: Page):
    """Event handler redirect to a dynamic route works."""
    base = _navigate(frontend_path_app, page)

    page.click("#btn-redir-dynamic")
    expect(page.locator("#page-id")).to_contain_text("dynamic page")
    expect(page).to_have_url(f"{base}/dynamic/42")


def test_on_load_redirect_static(frontend_path_app: AppHarness, page: Page):
    """on_load redirect to a static page works (bouncer pattern)."""
    base = _navigate(frontend_path_app, page, "/bouncer-static")
    expect(page.locator("#page-id")).to_have_text("static page")
    expect(page).to_have_url(f"{base}/static-page")


def test_on_load_redirect_dynamic(frontend_path_app: AppHarness, page: Page):
    """on_load redirect to a dynamic page works (bouncer pattern)."""
    base = _navigate(frontend_path_app, page, "/bouncer-dynamic")
    expect(page.locator("#page-id")).to_contain_text("dynamic page")
    expect(page).to_have_url(f"{base}/dynamic/99")


def test_asset_image_loads(frontend_path_app: AppHarness, page: Page):
    """An image from the assets directory loads correctly."""
    _navigate(frontend_path_app, page)

    img = page.locator("#asset-img")
    expect(img).to_be_visible()
    page.wait_for_function("document.querySelector('#asset-img').naturalWidth > 0")


def test_shared_asset_image_loads(frontend_path_app: AppHarness, page: Page):
    """A shared (library-style) asset image loads correctly."""
    _navigate(frontend_path_app, page)

    img = page.locator("#shared-asset-img")
    expect(img).to_be_visible()
    page.wait_for_function(
        "document.querySelector('#shared-asset-img').naturalWidth > 0"
    )


def test_css_background_image_loads(frontend_path_app: AppHarness, page: Page):
    """An external CSS file referencing an image via url() loads correctly."""
    _navigate(frontend_path_app, page)

    el = page.locator("#css-bg-image")
    expect(el).to_be_visible()
    expect(el).not_to_have_css("background-image", "none")


def test_uploaded_file_image_loads(frontend_path_app: AppHarness, page: Page):
    """An image served from the upload directory loads correctly."""
    _navigate(frontend_path_app, page)

    img = page.locator("#upload-img")
    expect(img).to_be_visible()
    page.wait_for_function("document.querySelector('#upload-img').naturalWidth > 0")


def test_uploaded_file_download(frontend_path_app: AppHarness, page: Page):
    """A file in the upload directory can be downloaded via get_upload_url link."""
    _navigate(frontend_path_app, page)

    link = page.locator("#upload-link")
    expect(link).to_be_visible()
    href = link.get_attribute("href")
    assert href is not None

    resp = httpx.get(href, follow_redirects=True)
    assert resp.status_code == 200
    assert resp.text == "uploaded file content"


# @pytest.mark.ignore_console_error
def test_404_page(frontend_path_app: AppHarness, page: Page):
    """Navigating to a non-existent page shows the 404 page."""
    base = frontend_path_app.frontend_url
    assert base is not None
    page.goto(f"{base.rstrip('/')}/this-page-does-not-exist")
    expect(page.get_by_text("404")).to_be_visible(timeout=10000)


def test_navigate_back_and_forth(frontend_path_app: AppHarness, page: Page):
    """Navigate between pages and verify on_load fires each time."""
    base = _navigate(frontend_path_app, page)
    expect(page.locator("#page-id")).to_have_text("index page")

    # index -> static
    page.click("#link-static")
    expect(page.locator("#page-id")).to_have_text("static page")
    expect(page).to_have_url(f"{base}/static-page")

    # static -> dynamic/7
    page.click("#link-dynamic")
    expect(page.locator("#page-id")).to_contain_text("dynamic page")
    expect(page).to_have_url(f"{base}/dynamic/7")

    # dynamic/7 -> index (via link-home)
    page.click("#link-home")
    expect(page.locator("#page-id")).to_have_text("index page")

    # Verify on_load fired for each navigation.
    log = page.locator("#on-load-log")
    expect(log).to_contain_text("index")
    expect(log).to_contain_text("static")
    expect(log).to_contain_text("dynamic-7")
