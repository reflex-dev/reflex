"""Integration tests for router URL/query sync and navigation semantics.

Reproduces and guards https://github.com/reflex-dev/reflex/issues/6603 and
codifies the agreed behavior of the navigation primitives:

* A direct ``rx.call_script(window.history.replaceState(...))`` changes the
  browser URL but is **not** a navigation: it fires no event, no ``on_load``,
  and does not reactively update the router. The corrected URL/query is simply
  observed by the **next** event sent to the backend (React Router's location
  does not see direct history manipulation, so the frontend reads the live
  ``window.location`` query when building ``router_data``).
* ``rx.redirect(target)`` performs a client-side navigation (push), fires
  ``on_load``, and updates the router reactively with no further interaction.
* ``rx.redirect(target, replace=True)`` behaves the same but replaces the
  current history entry instead of pushing a new one.

Covers dev and prod modes via ``app_harness_env`` parametrisation.
"""

from __future__ import annotations

import re
from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def RouterQueryApp():
    """App exercising replaceState, redirect, and redirect(replace=True)."""
    import reflex as rx

    class RouterQueryState(rx.State):
        # Incremented by the page on_load handler; proves whether a navigation
        # (and thus on_load) actually fired.
        load_count: int = 0
        # Incremented by an explicit, non-navigation event used to flush the
        # next round-trip to the backend.
        ping_count: int = 0

        @rx.var
        def query_str(self) -> str:
            """The raw router query string (recomputes when the router changes).

            Returns:
                The raw query string, without a leading ``?``.
            """
            return self.router.url.query

        @rx.var
        def name_param(self) -> str:
            """The ``name`` query parameter from the router.

            Returns:
                The value of the ``name`` query parameter, or ``""``.
            """
            return self.router.url.query_parameters.get("name", "")

        @rx.event
        def on_load(self):
            """Record that the page on_load handler fired."""
            self.load_count += 1

        @rx.event
        def replace_via_script(self, query: str):
            """Change the URL query via history.replaceState (not a navigation).

            Args:
                query: The query string to set (e.g. ``?name=test``).

            Returns:
                A call_script event that runs window.history.replaceState.
            """
            return rx.call_script(f"window.history.replaceState({{}}, '', {query!r})")

        @rx.event
        def ping(self):
            """Send an explicit, non-navigation event to the backend."""
            self.ping_count += 1

        @rx.event
        def do_redirect(self, target: str):
            """Navigate to target via rx.redirect (pushes a history entry).

            Args:
                target: The path to redirect to.

            Returns:
                A redirect event.
            """
            return rx.redirect(target)

        @rx.event
        def do_redirect_replace(self, target: str):
            """Navigate to target via rx.redirect(replace=True).

            Args:
                target: The path to redirect to.

            Returns:
                A redirect event that replaces the current history entry.
            """
            return rx.redirect(target, replace=True)

    def index():
        return rx.box(
            rx.input(
                value=RouterQueryState.router.session.client_token,
                read_only=True,
                id="token",
            ),
            rx.button(
                "replaceState ?name=test",
                on_click=RouterQueryState.replace_via_script("?name=test"),
                id="set-name-test",
            ),
            rx.button("ping", on_click=RouterQueryState.ping, id="ping"),
            rx.button(
                "redirect ?name=one",
                on_click=RouterQueryState.do_redirect("/?name=one"),
                id="redirect-one",
            ),
            rx.button(
                "redirect ?name=two",
                on_click=RouterQueryState.do_redirect("/?name=two"),
                id="redirect-two",
            ),
            rx.button(
                "redirect replace ?name=two",
                on_click=RouterQueryState.do_redirect_replace("/?name=two"),
                id="redirect-replace-two",
            ),
            rx.input(value=RouterQueryState.query_str, read_only=True, id="query-str"),
            rx.input(
                value=RouterQueryState.name_param, read_only=True, id="name-param"
            ),
            rx.input(
                value=f"{RouterQueryState.load_count}",
                read_only=True,
                id="load-count",
            ),
            rx.input(
                value=f"{RouterQueryState.ping_count}",
                read_only=True,
                id="ping-count",
            ),
        )

    app = rx.App()
    app.add_page(index, route="/", on_load=RouterQueryState.on_load)


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
    """Navigate to the app root and wait for hydration and the first on_load.

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
    # The initial page load fires on_load exactly once.
    expect(page.locator("#load-count")).to_have_value("1")
    return base


def test_replace_state_is_not_reactive_but_next_event_syncs(
    router_query_app: AppHarness, page: Page
):
    """history.replaceState changes the URL without firing any event; the next
    event observes the updated query.
    """
    _load(router_query_app, page)
    expect(page.locator("#name-param")).to_have_value("")

    # replaceState updates the browser URL but is not a navigation.
    page.click("#set-name-test")
    expect(page).to_have_url(re.compile(r".*\?name=test$"))

    # No event was triggered: on_load did not fire and the router did not change.
    expect(page.locator("#load-count")).to_have_value("1")
    expect(page.locator("#name-param")).to_have_value("")
    expect(page.locator("#query-str")).to_have_value("")

    # The next event (a plain, non-navigation event) carries the updated URL,
    # so the router-dependent computed vars recompute - without on_load firing.
    page.click("#ping")
    expect(page.locator("#ping-count")).to_have_value("1")
    expect(page.locator("#name-param")).to_have_value("test")
    expect(page.locator("#query-str")).to_have_value("name=test")
    expect(page.locator("#load-count")).to_have_value("1")


def test_redirect_navigates_pushes_and_updates_router_reactively(
    router_query_app: AppHarness, page: Page
):
    """rx.redirect performs a client-side push navigation, fires on_load, and
    updates the router reactively without further interaction.
    """
    _load(router_query_app, page)

    # Redirect updates the URL and the router with no extra interaction.
    page.click("#redirect-one")
    expect(page).to_have_url(re.compile(r".*\?name=one$"))
    expect(page.locator("#name-param")).to_have_value("one")
    expect(page.locator("#load-count")).to_have_value("2")

    # A second redirect pushes another history entry.
    page.click("#redirect-two")
    expect(page).to_have_url(re.compile(r".*\?name=two$"))
    expect(page.locator("#name-param")).to_have_value("two")
    expect(page.locator("#load-count")).to_have_value("3")

    # Because redirect pushes, going back returns to the previous entry.
    page.go_back()
    expect(page).to_have_url(re.compile(r".*\?name=one$"))
    expect(page.locator("#name-param")).to_have_value("one")
    expect(page.locator("#load-count")).to_have_value("4")


def test_redirect_replace_replaces_history_entry(
    router_query_app: AppHarness, page: Page
):
    """rx.redirect(replace=True) updates the router reactively and fires
    on_load, but replaces the current history entry instead of pushing.
    """
    base = _load(router_query_app, page)

    # Push ?name=one, then replace it with ?name=two.
    page.click("#redirect-one")
    expect(page).to_have_url(re.compile(r".*\?name=one$"))
    expect(page.locator("#name-param")).to_have_value("one")

    page.click("#redirect-replace-two")
    expect(page).to_have_url(re.compile(r".*\?name=two$"))
    expect(page.locator("#name-param")).to_have_value("two")
    # replace=True still navigates, so on_load fires (1 initial + 2 redirects).
    expect(page.locator("#load-count")).to_have_value("3")

    # The ?name=two entry replaced ?name=one, so going back lands on "/" with no
    # query - not on ?name=one (which would indicate a push).
    page.go_back()
    expect(page).to_have_url(f"{base}/")
    expect(page.locator("#name-param")).to_have_value("")
    expect(page.locator("#query-str")).to_have_value("")
