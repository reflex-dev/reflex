"""Integration test for dynamic routes."""

from __future__ import annotations

from typing import Generator, Type

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness, AppHarnessProd


def DynamicRoute():
    """App for testing dynamic routes."""
    from typing import List

    import reflex as rx

    class DynamicState(rx.State):
        order: List[str] = []

        def on_load(self):
            page_data = f"{self.router.page.path}-{self.page_id or 'no page id'}"
            print(f"on_load: {page_data}")
            self.order.append(page_data)

        def on_load_redir(self):
            query_params = self.router.page.params
            page_data = f"on_load_redir-{query_params}"
            print(f"on_load_redir: {page_data}")
            self.order.append(page_data)
            return rx.redirect(f"/page/{query_params['page_id']}")

        @rx.var
        def next_page(self) -> str:
            try:
                return str(int(self.page_id) + 1)
            except ValueError:
                return "0"

    def index():
        return rx.fragment(
            # rx.input(
            #     value=DynamicState.router.session.client_token,
            #     read_only=True,
            #     id="token",
            # ),
            rx.input(value=rx.State.page_id, read_only=True, id="page_id"),  # type: ignore
            rx.input(
                value=DynamicState.router.page.raw_path, read_only=True, id="raw_path"
            ),
            rx.vstack(
                rx.link("index", href="/", id="link_index"),
                rx.link("page_X", href="/static/x", id="link_page_x"),
                rx.link(
                    "next",
                    href="/page/" + DynamicState.next_page,
                    id="link_page_next",  # type: ignore
                ),
                rx.link("missing", href="/missing", id="link_missing"),
            ),
            rx.list(  # type: ignore
                rx.foreach(
                    DynamicState.order,  # type: ignore
                    lambda i: rx.list_item(rx.text(i)),
                ),
                id="order",
            ),
            rx.list(  # type: ignore
                rx.foreach(
                    DynamicState.router.page.params,
                    lambda i: rx.list_item(
                        rx.text(f"{i[0]}: {i[1]}"),  # type: ignore
                    ),
                ),
                id="params",
            ),
        )

    class ArgState(rx.State):
        """The app state."""

        @rx.var
        def arg(self) -> int:
            return int(self.arg_str or 0)

    class ArgSubState(ArgState):
        @rx.var(cache=True)
        def cached_arg(self) -> int:
            return self.arg

        @rx.var(cache=True)
        def cached_arg_str(self) -> str:
            return self.arg_str

    @rx.page(route="/arg/[arg_str]")
    def arg() -> rx.Component:
        return rx.vstack(
            rx.data_list.root(
                rx.data_list.item(
                    rx.data_list.label("rx.State.arg_str (dynamic)"),
                    rx.data_list.value(rx.State.arg_str, id="state-arg_str"),  # type: ignore
                ),
                rx.data_list.item(
                    rx.data_list.label("ArgState.arg_str (dynamic) (inherited)"),
                    rx.data_list.value(ArgState.arg_str, id="argstate-arg_str"),  # type: ignore
                ),
                rx.data_list.item(
                    rx.data_list.label("ArgState.arg"),
                    rx.data_list.value(ArgState.arg, id="argstate-arg"),
                ),
                rx.data_list.item(
                    rx.data_list.label("ArgSubState.arg_str (dynamic) (inherited)"),
                    rx.data_list.value(ArgSubState.arg_str, id="argsubstate-arg_str"),  # type: ignore
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

    @rx.page(route="/redirect-page/[page_id]", on_load=DynamicState.on_load_redir)  # type: ignore
    def redirect_page():
        return rx.fragment(rx.text("redirecting..."))

    app = rx.App(state=rx.State)
    app.add_page(index, route="/page/[page_id]", on_load=DynamicState.on_load)  # type: ignore
    app.add_page(index, route="/static/x", on_load=DynamicState.on_load)  # type: ignore
    app.add_page(index)
    app.add_custom_404_page(index, on_load=DynamicState.on_load)  # type: ignore


@pytest.fixture(scope="module")
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
        root=tmp_path_factory.mktemp("dynamic_route"),
        app_name=f"dynamicroute_{app_harness_env.__name__.lower()}",
        app_source=DynamicRoute,
    ) as harness:
        yield harness


def test_on_load_navigate(dynamic_route: AppHarness, page: Page):
    assert dynamic_route.frontend_url is not None
    is_prod = isinstance(dynamic_route, AppHarnessProd)

    page.goto(dynamic_route.frontend_url)

    # click the next link 10 times
    exp_order = [f"/page/[page_id]-{ix}" for ix in range(10)]
    link = page.locator("#link_page_next")
    for ix in range(10):
        link.click()
        expect(page.locator("#page_id")).to_have_value(str(ix))
        expect(page).to_have_url(dynamic_route.frontend_url + f"/page/{ix}/")

    order = page.locator("#order")
    expect(order).to_have_text("".join(exp_order))

    # manually load the next page to trigger client side routing in prod mode
    if is_prod:
        exp_order += ["/404-no page id"]
    exp_order += ["/page/[page_id]-10"]
    page.goto(dynamic_route.frontend_url + "/page/10/")
    expect(order).to_have_text("".join(exp_order))

    # make sure internal nav still hydrates after redirect
    exp_order += ["/page/[page_id]-11"]
    link.click()
    expect(order).to_have_text("".join(exp_order))

    # load same page with a query param and make sure it passes through
    if is_prod:
        exp_order += ["/404-no page id"]
    exp_order += ["/page/[page_id]-11"]
    page.goto(f"{page.url}?foo=bar")
    expect(order).to_have_text("".join(exp_order))

    params = page.locator("#params")
    params_str = params.text_content()
    assert params_str and "foo: bar" in params_str

    # test 404 page and make sure we hydrate
    exp_order += ["/404-no page id"]
    page.goto(dynamic_route.frontend_url + "/missing")
    expect(page).to_have_url(dynamic_route.frontend_url + "/missing/")
    # At that point we're on the 404 page, so #order is not rendered
    expect(order).to_have_text("".join(exp_order))

    # browser nav should still trigger hydration
    if is_prod:
        exp_order += ["/404-no page id"]
    exp_order += ["/page/[page_id]-11"]
    page.go_back()
    expect(order).to_have_text("".join(exp_order))

    # next/link to a 404 and ensure we still hydrate
    exp_order += ["/404-no page id"]
    missing_link = page.locator("#link_missing")
    missing_link.click()
    expect(order).to_have_text("".join(exp_order))

    # hit a page that redirects back to dynamic page
    if is_prod:
        exp_order += ["/404-no page id"]
    exp_order += ["on_load_redir-{'foo': 'bar', 'page_id': '0'}", "/page/[page_id]-0"]
    page.goto(dynamic_route.frontend_url + "/redirect-page/0/")

    # # should have redirected to page 0
    # expect(page).to_have_url(dynamic_route.frontend_url + "/page/0/")
