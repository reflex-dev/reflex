"""Regressions for navigation while the initial websocket is connecting."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, WebSocketRoute, expect

from reflex.testing import AppHarness


def NavigationBeforeConnectApp():
    """App whose first route redirects if its stale on_load runs."""
    import reflex as rx

    class NavigationState(rx.State):
        loads: list[str] = []

        @rx.event
        def slow_load(self):
            self.loads.append("slow")
            return rx.redirect("/hijack")

        @rx.event
        def other_load(self):
            self.loads.append("other")

    app = rx.App()

    def page_content():
        return rx.vstack(
            rx.foreach(NavigationState.loads, lambda item: rx.text(item)),
            rx.link("Other", href="/other", id="other-link"),
        )

    app.add_page(page_content, route="/slow", on_load=NavigationState.slow_load)
    app.add_page(page_content, route="/other", on_load=NavigationState.other_load)
    app.add_page(page_content, route="/hijack")


@pytest.fixture(scope="module")
def navigation_before_connect_app(
    app_harness_env: type[AppHarness],
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Start the app in dev or production mode.

    Yields:
        The running app harness.
    """
    with app_harness_env.create(
        root=tmp_path_factory.mktemp("navigation_before_connect"),
        app_name=f"navigationbeforeconnect_{app_harness_env.__name__.lower()}",
        app_source=NavigationBeforeConnectApp,
    ) as harness:
        yield harness


def test_navigation_before_socket_connect_uses_current_route(
    navigation_before_connect_app: AppHarness, page: Page
):
    """A delayed connect must not run the old page's on_load or redirect."""
    assert navigation_before_connect_app.frontend_url is not None
    frontend_url = navigation_before_connect_app.frontend_url.rstrip("/")
    sockets: list[WebSocketRoute] = []
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))

    def hold_socket(socket: WebSocketRoute) -> None:
        sockets.append(socket)

    page.route_web_socket("**/_event/**", hold_socket)

    page.goto(f"{frontend_url}/slow")
    expect(page.get_by_role("link", name="Other")).to_be_visible()
    if not sockets:
        with page.expect_websocket(timeout=60000):
            page.wait_for_timeout(100)
    assert len(sockets) == 1, page_errors

    page.get_by_role("link", name="Other").click()
    expect(page).to_have_url(f"{frontend_url}/other")

    sockets[0].connect_to_server()

    expect(page.locator("body")).to_contain_text("other")
    expect(page.get_by_text("other", exact=True)).to_have_count(1)
    expect(page).to_have_url(f"{frontend_url}/other")
    expect(page.locator("body")).not_to_contain_text("slow")
