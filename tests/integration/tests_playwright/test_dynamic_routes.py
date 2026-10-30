"""Integration tests for dynamic route page behavior."""

from __future__ import annotations

import json
import re
from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness, AppHarnessProd
from tests.integration.utils import (
    click_element,
    poll_assert_event_order,
    poll_for_navigation,
)


def DynamicRoute():
    """App for testing dynamic routes."""
    import reflex as rx

    class DynamicState(rx.State):
        order: list[str] = []

        @rx.event
        def on_load(self):
            page_data = f"{self.router.page.path}-{self.page_id or 'no page id'}"  # pyright: ignore[reportAttributeAccessIssue]
            print(f"on_load: {page_data}")
            self.order.append(page_data)

        @rx.event
        def on_load_redir(self):
            query_params = self.router.page.params
            page_data = f"on_load_redir-{query_params}"
            print(f"on_load_redir: {page_data}")
            self.order.append(page_data)
            return rx.redirect(f"/page/{query_params['page_id']}")

        @rx.event
        def on_load_static(self):
            print("on_load_static")
            self.order.append("on-load-static")

        @rx.var
        def next_page(self) -> str:
            try:
                return str(int(self.page_id) + 1)  # pyright: ignore[reportAttributeAccessIssue]
            except ValueError:
                return "0"

        @rx.var
        def params(self) -> dict[str, str | list[str]]:
            return self.router.page.params

    def index():
        return rx.fragment(
            rx.input(
                value=DynamicState.router.session.client_token,
                read_only=True,
                id="token",
            ),
            rx.input(value=rx.State.page_id, read_only=True, id="page_id"),  # pyright: ignore [reportAttributeAccessIssue]
            rx.input(
                value=DynamicState.router.page.raw_path,
                read_only=True,
                id="raw_path",
            ),
            rx.link("index", href="/", id="link_index"),
            rx.link("page_X", href="/static/x", id="link_page_x"),
            rx.link(
                "next",
                href="/page/" + DynamicState.next_page,
                id="link_page_next",
            ),
            rx.link("missing", href="/missing", id="link_missing"),
            rx.vstack(
                rx.foreach(
                    DynamicState.order,  # pyright: ignore [reportAttributeAccessIssue]
                    rx.text,
                ),
                id="event_order",
            ),
            rx.text(DynamicState.params.to_string(), id="params"),
        )

    class ArgState(rx.State):
        """The app state."""

        @rx.var(cache=False)
        def arg(self) -> int:
            return int(self.arg_str or 0)  # pyright: ignore[reportAttributeAccessIssue]

    class ArgSubState(ArgState):
        @rx.var
        def cached_arg(self) -> int:
            return self.arg

        @rx.var
        def cached_arg_str(self) -> str:
            return self.arg_str  # pyright: ignore[reportAttributeAccessIssue]

    @rx.page(route="/arg/[arg_str]")
    def arg() -> rx.Component:
        return rx.vstack(
            rx.input(
                value=DynamicState.router.session.client_token,
                read_only=True,
                id="token",
            ),
            rx.data_list.root(
                rx.data_list.item(
                    rx.data_list.label("rx.State.arg_str (dynamic)"),
                    rx.data_list.value(rx.State.arg_str, id="state-arg_str"),  # pyright: ignore [reportAttributeAccessIssue]
                ),
                rx.data_list.item(
                    rx.data_list.label("ArgState.arg_str (dynamic) (inherited)"),
                    rx.data_list.value(ArgState.arg_str, id="argstate-arg_str"),  # pyright: ignore [reportAttributeAccessIssue]
                ),
                rx.data_list.item(
                    rx.data_list.label("ArgState.arg"),
                    rx.data_list.value(ArgState.arg, id="argstate-arg"),
                ),
                rx.data_list.item(
                    rx.data_list.label("ArgSubState.arg_str (dynamic) (inherited)"),
                    rx.data_list.value(ArgSubState.arg_str, id="argsubstate-arg_str"),  # pyright: ignore [reportAttributeAccessIssue]
                ),
                rx.data_list.item(
                    rx.data_list.label("ArgSubState.arg (inherited)"),
                    rx.data_list.value(ArgSubState.arg, id="argsubstate-arg"),
                ),
                rx.data_list.item(
                    rx.data_list.label("ArgSubState.cached_arg"),
                    rx.data_list.value(
                        ArgSubState.cached_arg, id="argsubstate-cached_arg"
                    ),
                ),
                rx.data_list.item(
                    rx.data_list.label("ArgSubState.cached_arg_str"),
                    rx.data_list.value(
                        ArgSubState.cached_arg_str, id="argsubstate-cached_arg_str"
                    ),
                ),
            ),
            rx.link("+", href=f"/arg/{ArgState.arg + 1}", id="next-page"),
            align="center",
            height="100vh",
        )

    @rx.page(route="/redirect-page/[page_id]", on_load=DynamicState.on_load_redir)
    def redirect_page():
        return rx.fragment(rx.text("redirecting..."))

    app = rx.App()
    app.add_page(index, route="/page/[page_id]", on_load=DynamicState.on_load)
    app.add_page(index, route="/page/static", on_load=DynamicState.on_load_static)
    app.add_page(index, route="/static/x", on_load=DynamicState.on_load)
    app.add_page(index)
    app.add_page(route="/404", on_load=DynamicState.on_load)


@pytest.fixture(scope="module")
def dynamic_route(
    app_harness_env: type[AppHarness], tmp_path_factory
) -> Generator[AppHarness, None, None]:
    """Start DynamicRoute app at tmp_path via AppHarness.

    Args:
        app_harness_env: either AppHarness (dev) or AppHarnessProd (prod)
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    with app_harness_env.create(
        root=tmp_path_factory.mktemp("dynamic_route"),
        app_name=f"dynamicroute_{app_harness_env.__name__.lower()}",
        app_source=DynamicRoute,
    ) as harness:
        yield harness


@pytest.fixture
def driver(dynamic_route: AppHarness, page: Page) -> Page:
    """Open the app and wait until the browser is connected to its state.

    Returns:
        The connected Playwright page.
    """
    assert dynamic_route.frontend_url is not None
    page.goto(dynamic_route.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")
    return page


@pytest.fixture
def token(driver: Page) -> str:
    """Get the token associated with backend state.

    Args:
        driver: Playwright page.

    Returns:
        The token visible in the driver browser.
    """
    return driver.locator("#token").input_value()


def test_on_load_navigate(
    dynamic_route: AppHarness,
    driver: Page,
):
    """Click links to navigate between dynamic pages with on_load event.

    Args:
        dynamic_route: harness for DynamicRoute app.
        driver: Playwright page.
    """
    assert dynamic_route.app_instance is not None

    exp_order = [f"/page/[page_id]-{ix}" for ix in range(10)]
    # click the link a few times
    for ix in range(10):
        # wait for navigation, then assert on url
        with poll_for_navigation(driver):
            click_element(driver, "#link_page_next")
        expect(driver).to_have_url(re.compile(rf".*/page/{ix}$"))

        expect(driver.locator("#page_id")).to_have_value(str(ix))
        expect(driver.locator("#raw_path")).to_have_value(f"/page/{ix}")
    poll_assert_event_order(driver, exp_order)

    frontend_url = dynamic_route.frontend_url
    assert frontend_url
    frontend_url = frontend_url.removesuffix("/")

    # manually load the next page to trigger client side routing in prod mode
    exp_order += ["/page/[page_id]-10"]
    with poll_for_navigation(driver):
        driver.goto(f"{frontend_url}/page/10")
    poll_assert_event_order(driver, exp_order)

    # make sure internal nav still hydrates after redirect
    exp_order += ["/page/[page_id]-11"]
    with poll_for_navigation(driver):
        click_element(driver, "#link_page_next")
    poll_assert_event_order(driver, exp_order)

    # load same page with a query param and make sure it passes through
    exp_order += ["/page/[page_id]-11"]
    with poll_for_navigation(driver):
        driver.goto(f"{driver.url}?foo=bar")
    poll_assert_event_order(driver, exp_order)
    params_json = driver.locator("#params")
    params = json.loads(params_json.inner_text())
    assert params == {"foo": "bar", "page_id": "11"}

    # Check the server response and browser-history hydration separately. A
    # dev SPA fallback may or may not emit 404 on_load for a full-page load;
    # the client-side missing-link case below verifies that event reliably.
    order_before_missing = exp_order.copy()
    with poll_for_navigation(driver):
        response = driver.goto(f"{frontend_url}/missing")
    assert response is not None
    if isinstance(dynamic_route, AppHarnessProd):
        assert response.status == 404
        direct_missing_orders = [order_before_missing]
    else:
        assert response.status == 200
        direct_missing_orders = [
            order_before_missing,
            [*order_before_missing, "/404-no page id"],
        ]

    # browser nav should still trigger hydration
    with poll_for_navigation(driver):
        driver.go_back()
    expected_back_orders = [
        [*order, "/page/[page_id]-11"] for order in direct_missing_orders
    ]
    driver.wait_for_function(
        """(orders) => {
            const texts = Array.from(
                document.querySelectorAll('#event_order > p'),
                (paragraph) => paragraph.textContent,
            );
            return orders.some((order) => JSON.stringify(order) === JSON.stringify(texts));
        }""",
        arg=expected_back_orders,
    )
    exp_order = driver.locator("#event_order > p").all_text_contents()
    assert exp_order in expected_back_orders

    # next/link to a 404 and ensure we still hydrate
    exp_order += ["/404-no page id"]
    with poll_for_navigation(driver):
        click_element(driver, "#link_missing")

    # hit a page that redirects back to dynamic page
    exp_order += ["on_load_redir-{'foo': 'bar', 'page_id': '0'}", "/page/[page_id]-0"]
    with poll_for_navigation(driver):
        driver.goto(f"{frontend_url}/redirect-page/0/?foo=bar")
    poll_assert_event_order(driver, exp_order)
    # should have redirected back to page 0
    expect(driver).to_have_url(re.compile(r".*/page/0$"))

    # hit a static route that would also match the dynamic route
    exp_order += ["on-load-static"]
    with poll_for_navigation(driver):
        driver.goto(f"{frontend_url}/page/static")
    poll_assert_event_order(driver, exp_order)


def test_on_load_navigate_non_dynamic(
    dynamic_route: AppHarness,
    driver: Page,
):
    """Click links to navigate between static pages with on_load event.

    Args:
        dynamic_route: harness for DynamicRoute app.
        driver: Playwright page.
    """
    assert dynamic_route.app_instance is not None

    with poll_for_navigation(driver):
        click_element(driver, "#link_page_x")
    expect(driver).to_have_url(re.compile(r".*/static/x$"))
    poll_assert_event_order(driver, ["/static/x-no page id"])

    # go back to the index and navigate back to the static route
    with poll_for_navigation(driver):
        click_element(driver, "#link_index")
    expect(driver).to_have_url(re.compile(r".*/$"))

    with poll_for_navigation(driver):
        click_element(driver, "#link_page_x")
    expect(driver).to_have_url(re.compile(r".*/static/x$"))
    poll_assert_event_order(driver, ["/static/x-no page id", "/static/x-no page id"])

    for _ in range(3):
        click_element(driver, "#link_page_x")
        expect(driver).to_have_url(re.compile(r".*/static/x$"))
    poll_assert_event_order(driver, ["/static/x-no page id"] * 5)


def test_render_dynamic_arg(
    dynamic_route: AppHarness,
    driver: Page,
):
    """Assert that dynamic arg var is rendered correctly in different contexts.

    Args:
        dynamic_route: harness for DynamicRoute app.
        driver: Playwright page.
    """
    assert dynamic_route.app_instance is not None
    frontend_url = dynamic_route.frontend_url
    assert frontend_url

    with poll_for_navigation(driver):
        driver.goto(f"{frontend_url.removesuffix('/')}/arg/0")

    def assert_content(expected: str, previous: str):
        ids = [
            "state-arg_str",
            "argstate-arg",
            "argstate-arg_str",
            "argsubstate-arg_str",
            "argsubstate-arg",
            "argsubstate-cached_arg",
            "argsubstate-cached_arg_str",
        ]
        for id in ids:
            content = expect(driver.locator(f"#{id}"))
            content.not_to_have_text(previous, timeout=30_000)
            content.to_have_text(expected, timeout=30_000)

    assert_content("0", "")
    with poll_for_navigation(driver):
        click_element(driver, "#next-page")
    assert driver.url.rstrip("/") == f"{frontend_url.removesuffix('/')}/arg/1"
    assert_content("1", "0")
    with poll_for_navigation(driver):
        click_element(driver, "#next-page")
    assert driver.url.rstrip("/") == f"{frontend_url.removesuffix('/')}/arg/2"
    assert_content("2", "1")
