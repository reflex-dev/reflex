"""Integration tests for dynamic route page behavior."""
import time
from typing import Generator, Type
from urllib.parse import urlsplit

import pytest
from selenium.webdriver.common.by import By

from reflex.testing import AppHarness, AppHarnessProd

from .utils import poll_for_navigation


def DynamicRoute():
    """App for testing dynamic routes."""
    import reflex as rx

    class DynamicState(rx.State):
        order: list[str] = []
        page_id: str = ""

        def on_load(self):
            self.order.append(
                f"{self.get_current_page()}-{self.page_id or 'no page id'}"
            )

        def on_load_redir(self):
            query_params = self.get_query_params()
            self.order.append(f"on_load_redir-{query_params}")
            return rx.redirect(f"/page/{query_params['page_id']}")

        @rx.var
        def next_page(self) -> str:
            try:
                return str(int(self.page_id) + 1)
            except ValueError:
                return "0"

        @rx.var
        def token(self) -> str:
            return self.get_token()

    def index():
        return rx.fragment(
            rx.input(value=DynamicState.token, is_read_only=True, id="token"),
            rx.input(value=DynamicState.page_id, is_read_only=True, id="page_id"),
            rx.link("index", href="/", id="link_index"),
            rx.link("page_X", href="/static/x", id="link_page_x"),
            rx.link(
                "next", href="/page/" + DynamicState.next_page, id="link_page_next"  # type: ignore
            ),
            rx.link("missing", href="/missing", id="link_missing"),
            rx.list(
                rx.foreach(DynamicState.order, lambda i: rx.list_item(rx.text(i))),  # type: ignore
            ),
        )

    @rx.page(route="/redirect-page/[page_id]", on_load=DynamicState.on_load_redir)  # type: ignore
    def redirect_page():
        return rx.fragment(rx.text("redirecting..."))

    app = rx.App(state=DynamicState)
    app.add_page(index)
    app.add_page(index, route="/page/[page_id]", on_load=DynamicState.on_load)  # type: ignore
    app.add_page(index, route="/static/x", on_load=DynamicState.on_load)  # type: ignore
    app.add_custom_404_page(on_load=DynamicState.on_load)  # type: ignore
    app.compile()


@pytest.fixture(scope="session")
def dynamic_route(
    app_harness_env: Type[AppHarness], tmp_path_factory
) -> Generator[AppHarness, None, None]:
    """Start DynamicRoute app at tmp_path via AppHarness.

    Args:
        app_harness_env: either AppHarness (dev) or AppHarnessProd (prod)
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    with app_harness_env.create(
        root=tmp_path_factory.mktemp(f"dynamic_route"),
        app_source=DynamicRoute,  # type: ignore
    ) as harness:
        yield harness


@pytest.fixture
def driver(dynamic_route: AppHarness):
    """Get an instance of the browser open to the dynamic_route app.

    Args:
        dynamic_route: harness for DynamicRoute app

    Yields:
        WebDriver instance.
    """
    assert dynamic_route.app_instance is not None, "app is not running"
    driver = dynamic_route.frontend()
    try:
        assert dynamic_route.poll_for_clients()
        yield driver
    finally:
        driver.quit()


def test_on_load_navigate(dynamic_route: AppHarness, driver):
    """Click links to navigate between dynamic pages with on_load event.

    Args:
        dynamic_route: harness for DynamicRoute app.
        driver: WebDriver instance.
    """
    assert dynamic_route.app_instance is not None
    is_prod = isinstance(dynamic_route, AppHarnessProd)
    token_input = driver.find_element(By.ID, "token")
    link = driver.find_element(By.ID, "link_page_next")
    assert token_input
    assert link

    # wait for the backend connection to send the token
    token = dynamic_route.poll_for_value(token_input)
    assert token is not None

    exp_order = [f"/page/[page-id]-{ix}" for ix in range(10)]

    # click the link a few times
    for ix in range(10):
        # wait for navigation, then assert on url
        with poll_for_navigation(driver):
            link.click()
        assert urlsplit(driver.current_url).path == f"/page/{ix}/"

        link = driver.find_element(By.ID, "link_page_next")
        page_id_input = driver.find_element(By.ID, "page_id")

        assert link
        assert page_id_input

        assert dynamic_route.poll_for_value(page_id_input) == str(ix)

    # look up the backend state and assert that `on_load` was called for all
    # navigation events
    backend_state = dynamic_route.app_instance.state_manager.states[token]
    time.sleep(0.2)
    assert backend_state.order == exp_order

    # manually load the next page to trigger client side routing in prod mode
    if is_prod:
        exp_order += ["/404-no page id"]
    exp_order += ["/page/[page-id]-10"]
    with poll_for_navigation(driver):
        driver.get(f"{dynamic_route.frontend_url}/page/10/")
    time.sleep(0.2)
    assert backend_state.order == exp_order

    # make sure internal nav still hydrates after redirect
    exp_order += ["/page/[page-id]-11"]
    link = driver.find_element(By.ID, "link_page_next")
    with poll_for_navigation(driver):
        link.click()
    time.sleep(0.2)
    assert backend_state.order == exp_order

    # load same page with a query param and make sure it passes through
    if is_prod:
        exp_order += ["/404-no page id"]
    exp_order += ["/page/[page-id]-11"]
    with poll_for_navigation(driver):
        driver.get(f"{driver.current_url}?foo=bar")
    time.sleep(0.2)
    assert backend_state.get_query_params()["foo"] == "bar"
    assert backend_state.order == exp_order

    # hit a 404 and ensure we still hydrate
    exp_order += ["/404-no page id"]
    with poll_for_navigation(driver):
        driver.get(f"{dynamic_route.frontend_url}/missing")
    time.sleep(0.5)
    assert backend_state.order == exp_order

    # browser nav should still trigger hydration
    if is_prod:
        exp_order += ["/404-no page id"]
    exp_order += ["/page/[page-id]-11"]
    with poll_for_navigation(driver):
        driver.back()
    time.sleep(0.2)
    assert backend_state.order == exp_order

    # next/link to a 404 and ensure we still hydrate
    exp_order += ["/404-no page id"]
    link = driver.find_element(By.ID, "link_missing")
    with poll_for_navigation(driver):
        link.click()
    time.sleep(0.5)
    assert backend_state.order == exp_order

    # hit a page that redirects back to dynamic page
    if is_prod:
        exp_order += ["/404-no page id"]
    exp_order += ["on_load_redir-{'foo': 'bar', 'page_id': '0'}", "/page/[page-id]-0"]
    with poll_for_navigation(driver):
        driver.get(f"{dynamic_route.frontend_url}/redirect-page/0/?foo=bar")
    time.sleep(0.5)
    assert backend_state.order == exp_order
    # should have redirected back to page 0
    assert urlsplit(driver.current_url).path == "/page/0/"


def test_on_load_navigate_non_dynamic(dynamic_route: AppHarness, driver):
    """Click links to navigate between static pages with on_load event.

    Args:
        dynamic_route: harness for DynamicRoute app.
        driver: WebDriver instance.
    """
    assert dynamic_route.app_instance is not None
    token_input = driver.find_element(By.ID, "token")
    link = driver.find_element(By.ID, "link_page_x")
    assert token_input
    assert link

    # wait for the backend connection to send the token
    token = dynamic_route.poll_for_value(token_input)
    assert token is not None

    with poll_for_navigation(driver):
        link.click()
    assert urlsplit(driver.current_url).path == "/static/x/"

    # look up the backend state and assert that `on_load` was called once
    backend_state = dynamic_route.app_instance.state_manager.states[token]
    time.sleep(0.2)
    assert backend_state.order == ["/static/x-no page id"]

    # go back to the index and navigate back to the static route
    link = driver.find_element(By.ID, "link_index")
    with poll_for_navigation(driver):
        link.click()
    assert urlsplit(driver.current_url).path == "/"

    link = driver.find_element(By.ID, "link_page_x")
    with poll_for_navigation(driver):
        link.click()
    assert urlsplit(driver.current_url).path == "/static/x/"
    time.sleep(0.2)
    assert backend_state.order == ["/static/x-no page id", "/static/x-no page id"]
