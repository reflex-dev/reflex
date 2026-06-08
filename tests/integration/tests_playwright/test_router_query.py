"""Integration test for router query sync after history.replaceState.

Reproduces https://github.com/reflex-dev/reflex/issues/6603: updating the URL
query string with ``window.history.replaceState`` (e.g. via ``rx.call_script``)
should keep ``State.router.url.query`` in sync. React Router's ``useLocation``
does not observe direct history manipulation, so the frontend must read the
live ``window.location`` query when populating ``router_data``.

Covers dev and prod modes via ``app_harness_env`` parametrisation.
"""

from __future__ import annotations

import re
from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def RouterQueryApp():
    """App that mutates the URL query via replaceState and reads it back."""
    import reflex as rx

    class RouterQueryState(rx.State):
        # The raw query string read from the router on the last read event.
        query_str: str = ""
        # The "name" query parameter read from the router on the last read event.
        name_param: str = ""

        @rx.event
        def replace_query(self, query: str):
            """Update the browser URL query string without going through React Router.

            Args:
                query: The query string to set (e.g. ``?name=test``).

            Returns:
                A call_script event that runs window.history.replaceState.
            """
            return rx.call_script(f"window.history.replaceState({{}}, '', {query!r})")

        @rx.event
        def read_query(self):
            """Read the current router query into state vars."""
            self.query_str = self.router.url.query
            self.name_param = self.router.url.query_parameters.get("name", "")

    def index():
        return rx.box(
            rx.input(
                value=RouterQueryState.router.session.client_token,
                read_only=True,
                id="token",
            ),
            rx.button(
                "set ?name=test",
                on_click=RouterQueryState.replace_query("?name=test"),
                id="set-name-test",
            ),
            rx.button(
                "set ?name=other&page=2",
                on_click=RouterQueryState.replace_query("?name=other&page=2"),
                id="set-name-other",
            ),
            rx.button(
                "read query",
                on_click=RouterQueryState.read_query,
                id="read-query",
            ),
            rx.input(value=RouterQueryState.query_str, read_only=True, id="query-str"),
            rx.input(
                value=RouterQueryState.name_param, read_only=True, id="name-param"
            ),
        )

    app = rx.App()
    app.add_page(index)


@pytest.fixture(scope="module")
def router_query_app(
    app_harness_env: type[AppHarness],
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Start the RouterQueryApp in dev or prod mode.

    Args:
        app_harness_env: AppHarness (dev) or AppHarnessProd (prod).
        tmp_path_factory: pytest fixture for creating temporary directories.

    Yields:
        Running AppHarness instance.
    """
    name = f"routerquery_{app_harness_env.__name__.lower()}"
    with app_harness_env.create(
        root=tmp_path_factory.mktemp(name),
        app_name=name,
        app_source=RouterQueryApp,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


def _load(harness: AppHarness, page: Page) -> str:
    """Navigate to the app root and wait for hydration.

    Args:
        harness: The running AppHarness.
        page: Playwright page.

    Returns:
        The frontend base URL with any trailing slash stripped.
    """
    base = harness.frontend_url
    assert base is not None
    base = base.rstrip("/")
    page.goto(base)
    expect(page.locator("#token")).not_to_have_value("")
    return base


def test_replace_state_syncs_router_query(router_query_app: AppHarness, page: Page):
    """router.url.query reflects query params set via history.replaceState."""
    _load(router_query_app, page)

    # Baseline: no query yet.
    page.click("#read-query")
    expect(page.locator("#query-str")).to_have_value("")
    expect(page.locator("#name-param")).to_have_value("")

    # Update the URL query via replaceState (bypasses React Router).
    page.click("#set-name-test")
    expect(page).to_have_url(re.compile(r".*\?name=test$"))

    # The next event must carry the updated query to the backend.
    page.click("#read-query")
    expect(page.locator("#name-param")).to_have_value("test")
    expect(page.locator("#query-str")).to_have_value("name=test")

    # A subsequent replaceState keeps the router in sync.
    page.click("#set-name-other")
    expect(page).to_have_url(re.compile(r".*\?name=other&page=2$"))
    page.click("#read-query")
    expect(page.locator("#name-param")).to_have_value("other")
    expect(page.locator("#query-str")).to_have_value("name=other&page=2")
