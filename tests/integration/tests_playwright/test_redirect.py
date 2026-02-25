from typing import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def RedirectRoute():
    """App for testing redirects."""
    import reflex as rx

    class RedirectState(rx.State):
        redirected: bool = False
        order: list[str] = []

        def on_load(self):
            self.redirected = True
            page_data = f"{self.router.page.path}-{self.page_id or 'no page id'}"
            print(f"on_load: {page_data}")
            self.order.append(page_data)

        def on_load_redir(self):
            page_id = self.router.page.params["page_id"]
            return rx.redirect(f"/redirected/{page_id}")

    app = rx.App(state=rx.State)

    def index():
        return rx.fragment(
            rx.link("redirect", href="/redirect-page/3", id="link_redirect"),
            rx.ordered_list(
                rx.foreach(RedirectState.order, rx.text),
            ),
        )

    # reuse the same page, only the URL interests us
    app.add_page(index, "index")
    app.add_page(index, "redirect-page/[page_id]", on_load=RedirectState.on_load_redir)
    app.add_page(index, "redirected/[page_id]", on_load=RedirectState.on_load)


@pytest.fixture(scope="module")
def redirect_repro(tmp_path_factory) -> Generator[AppHarness, None, None]:
    with AppHarness.create(
        app_source=RedirectRoute,
        root=tmp_path_factory.mktemp("redirect_repro"),
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


def test_redirect(redirect_repro: AppHarness, page: Page):
    assert redirect_repro.frontend_url is not None
    page.goto(redirect_repro.frontend_url)

    # by clicking the link, we should be redirected to /redirected
    page.click("#link_redirect")
    expect(page).to_have_url(redirect_repro.frontend_url + "/redirected/3/")

    # return to index
    page.goto(redirect_repro.frontend_url)
    expect(page).to_have_url(redirect_repro.frontend_url + "/")

    page.goto(redirect_repro.frontend_url + "/redirect/3")
    expect(page).to_have_url(redirect_repro.frontend_url + "/redirected/3/")
