"""Integration tests for dynamic route page behavior."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine, Generator
from urllib.parse import urlsplit

import pytest
from selenium.webdriver.common.by import By

from reflex.testing import AppHarness, WebDriver

from .utils import poll_for_navigation


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
            rx.list(  # pyright: ignore [reportAttributeAccessIssue]
                rx.foreach(
                    DynamicState.order,  # pyright: ignore [reportAttributeAccessIssue]
                    lambda i: rx.list_item(rx.text(i)),
                ),
            ),
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
def driver(dynamic_route: AppHarness) -> Generator[WebDriver, None, None]:
    """Get an instance of the browser open to the dynamic_route app.

    Args:
        dynamic_route: harness for DynamicRoute app

    Yields:
        WebDriver instance.
    """
    assert dynamic_route.app_instance is not None, "app is not running"
    driver = dynamic_route.frontend()
    # TODO: drop after flakiness is resolved
    driver.implicitly_wait(30)
    try:
        yield driver
    finally:
        driver.quit()


@pytest.fixture
def token(dynamic_route: AppHarness, driver: WebDriver) -> str:
    """Get the token associated with backend state.

    Args:
        dynamic_route: harness for DynamicRoute app.
        driver: WebDriver instance.

    Returns:
        The token visible in the driver browser.
    """
    assert dynamic_route.app_instance is not None
    token_input = AppHarness.poll_for_or_raise_timeout(
        lambda: driver.find_element(By.ID, "token")
    )

    # wait for the backend connection to send the token
    token = dynamic_route.poll_for_value(token_input)
    assert token is not None

    return token


@pytest.fixture
def poll_for_order(
    dynamic_route: AppHarness, token: str
) -> Callable[[list[str]], Coroutine[None, None, None]]:
    """Poll for the order list to match the expected order.

    Args:
        dynamic_route: harness for DynamicRoute app.
        token: The token visible in the driver browser.

    Returns:
        An async function that polls for the order list to match the expected order.
    """
    dynamic_state_name = dynamic_route.get_state_name("_dynamic_state")
    dynamic_state_full_name = dynamic_route.get_full_state_name(["_dynamic_state"])

    async def _poll_for_order(exp_order: list[str]):
        async def _backend_state():
            return await dynamic_route.get_state(f"{token}_{dynamic_state_full_name}")

        async def _check():
            return (await _backend_state()).substates[
                dynamic_state_name
            ].order == exp_order  # pyright: ignore[reportAttributeAccessIssue]

        await AppHarness._poll_for_async(_check, timeout=10)
        assert (
            list((await _backend_state()).substates[dynamic_state_name].order)  # pyright: ignore[reportAttributeAccessIssue]
            == exp_order
        )

    return _poll_for_order


@pytest.mark.asyncio
async def test_on_load_navigate(
    dynamic_route: AppHarness,
    driver: WebDriver,
    token: str,
    poll_for_order: Callable[[list[str]], Coroutine[None, None, None]],
):
    """Click links to navigate between dynamic pages with on_load event.

    Args:
        dynamic_route: harness for DynamicRoute app.
        driver: WebDriver instance.
        token: The token visible in the driver browser.
        poll_for_order: function that polls for the order list to match the expected order.
    """
    dynamic_state_full_name = dynamic_route.get_full_state_name(["_dynamic_state"])
    assert dynamic_route.app_instance is not None
    link = driver.find_element(By.ID, "link_page_next")
    assert link

    exp_order = [f"/page/[page_id]-{ix}" for ix in range(10)]
    # click the link a few times
    for ix in range(10):
        # wait for navigation, then assert on url
        with poll_for_navigation(driver):
            link.click()
        assert urlsplit(driver.current_url).path == f"/page/{ix}"

        link = AppHarness.poll_for_or_raise_timeout(
            lambda: driver.find_element(By.ID, "link_page_next")
        )
        page_id_input = driver.find_element(By.ID, "page_id")
        raw_path_input = driver.find_element(By.ID, "raw_path")

        assert link
        assert page_id_input

        assert dynamic_route.poll_for_value(
            page_id_input, exp_not_equal=str(ix - 1)
        ) == str(ix)
        assert dynamic_route.poll_for_value(raw_path_input) == f"/page/{ix}"
    await poll_for_order(exp_order)

    frontend_url = dynamic_route.frontend_url
    assert frontend_url
    frontend_url = frontend_url.removesuffix("/")

    # manually load the next page to trigger client side routing in prod mode
    exp_order += ["/page/[page_id]-10"]
    with poll_for_navigation(driver):
        driver.get(f"{frontend_url}/page/10")
    await poll_for_order(exp_order)

    # make sure internal nav still hydrates after redirect
    exp_order += ["/page/[page_id]-11"]
    link = driver.find_element(By.ID, "link_page_next")
    with poll_for_navigation(driver):
        link.click()
    await poll_for_order(exp_order)

    # load same page with a query param and make sure it passes through
    exp_order += ["/page/[page_id]-11"]
    with poll_for_navigation(driver):
        driver.get(f"{driver.current_url}?foo=bar")
    await poll_for_order(exp_order)
    assert (
        await dynamic_route.get_state(f"{token}_{dynamic_state_full_name}")
    ).router.page.params["foo"] == "bar"

    # hit a 404 and ensure we still hydrate
    exp_order += ["/404-no page id"]
    with poll_for_navigation(driver):
        driver.get(f"{frontend_url}/missing")
    await poll_for_order(exp_order)

    # browser nav should still trigger hydration
    exp_order += ["/page/[page_id]-11"]
    with poll_for_navigation(driver):
        driver.back()
    await poll_for_order(exp_order)

    # next/link to a 404 and ensure we still hydrate
    exp_order += ["/404-no page id"]
    link = driver.find_element(By.ID, "link_missing")
    with poll_for_navigation(driver):
        link.click()
    await poll_for_order(exp_order)

    # hit a page that redirects back to dynamic page
    exp_order += ["on_load_redir-{'foo': 'bar', 'page_id': '0'}", "/page/[page_id]-0"]
    with poll_for_navigation(driver):
        driver.get(f"{frontend_url}/redirect-page/0/?foo=bar")
    await poll_for_order(exp_order)
    # should have redirected back to page 0
    assert urlsplit(driver.current_url).path.removesuffix("/") == "/page/0"

    # hit a static route that would also match the dynamic route
    exp_order += ["on-load-static"]
    with poll_for_navigation(driver):
        driver.get(f"{frontend_url}/page/static")
    await poll_for_order(exp_order)


@pytest.mark.asyncio
async def test_on_load_navigate_non_dynamic(
    dynamic_route: AppHarness,
    driver: WebDriver,
    poll_for_order: Callable[[list[str]], Coroutine[None, None, None]],
):
    """Click links to navigate between static pages with on_load event.

    Args:
        dynamic_route: harness for DynamicRoute app.
        driver: WebDriver instance.
        poll_for_order: function that polls for the order list to match the expected order.
    """
    assert dynamic_route.app_instance is not None
    link = driver.find_element(By.ID, "link_page_x")
    assert link

    with poll_for_navigation(driver):
        link.click()
    assert urlsplit(driver.current_url).path.removesuffix("/") == "/static/x"
    await poll_for_order(["/static/x-no page id"])

    # go back to the index and navigate back to the static route
    link = driver.find_element(By.ID, "link_index")
    with poll_for_navigation(driver):
        link.click()
    assert urlsplit(driver.current_url).path.removesuffix("/") == ""

    link = driver.find_element(By.ID, "link_page_x")
    with poll_for_navigation(driver):
        link.click()
    assert urlsplit(driver.current_url).path.removesuffix("/") == "/static/x"
    await poll_for_order(["/static/x-no page id", "/static/x-no page id"])

    for _ in range(3):
        link = driver.find_element(By.ID, "link_page_x")
        link.click()
        assert urlsplit(driver.current_url).path.removesuffix("/") == "/static/x"
    await poll_for_order(["/static/x-no page id"] * 5)


@pytest.mark.asyncio
async def test_render_dynamic_arg(
    dynamic_route: AppHarness,
    driver: WebDriver,
    token: str,
):
    """Assert that dynamic arg var is rendered correctly in different contexts.

    Args:
        dynamic_route: harness for DynamicRoute app.
        driver: WebDriver instance.
        token: The token visible in the driver browser.
    """
    assert dynamic_route.app_instance is not None
    frontend_url = dynamic_route.frontend_url
    assert frontend_url

    with poll_for_navigation(driver):
        driver.get(f"{frontend_url.removesuffix('/')}/arg/0")

    # TODO: drop after flakiness is resolved
    await asyncio.sleep(3)

    def assert_content(expected: str, expect_not: str):
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
            el = driver.find_element(By.ID, id)
            assert el
            assert (
                dynamic_route.poll_for_content(el, timeout=30, exp_not_equal=expect_not)
                == expected
            )

    assert_content("0", "")
    next_page_link = driver.find_element(By.ID, "next-page")
    assert next_page_link
    with poll_for_navigation(driver):
        next_page_link.click()
    assert (
        driver.current_url.removesuffix("/")
        == f"{frontend_url.removesuffix('/')}/arg/1"
    )
    assert_content("1", "0")
    next_page_link = driver.find_element(By.ID, "next-page")
    assert next_page_link
    with poll_for_navigation(driver):
        next_page_link.click()
    assert (
        driver.current_url.removesuffix("/")
        == f"{frontend_url.removesuffix('/')}/arg/2"
    )
    assert_content("2", "1")
