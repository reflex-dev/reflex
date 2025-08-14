from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.environment import environment
from reflex.testing import AppHarness, AppHarnessProd


def OnLoadRedirectApp():
    import reflex as rx

    @rx.page("/")
    def index():
        return rx.container(
            rx.input(
                value=rx.State.router.session.client_token,
                read_only=True,
                id="token",
            ),
            rx.vstack(
                rx.heading("This is the index page!"),
                rx.button("Go to Subpage!", on_click=rx.redirect("/subpage")),
            ),
        )

    @rx.page("/subpage")
    def subpage():
        return rx.container(
            rx.vstack(
                rx.heading("This is the sub page!"),
                rx.button("Go to index!", on_click=rx.redirect("/")),
                rx.button("Bounce to index!", on_click=rx.redirect("/bouncer")),
            )
        )

    @rx.page("/bouncer", on_load=rx.redirect("/"))
    def bouncer():
        return rx.container(
            rx.vstack(
                rx.heading("This is the bouncer page!"),
                rx.text("You should not be here!"),
                rx.button("Go to index!", on_click=rx.redirect("/")),
            ),
        )

    app = rx.App()  # noqa: F841


@pytest.fixture
def onload_redirect_app(tmp_path_factory) -> Generator[AppHarness, None, None]:
    with AppHarnessProd.create(
        root=tmp_path_factory.mktemp("frontend_path_app"),
        app_source=OnLoadRedirectApp,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


@pytest.fixture
def onload_redirect_with_prefix_app(
    tmp_path_factory,
) -> Generator[AppHarness, None, None]:
    prefix = "/prefix"
    try:
        environment.REFLEX_FRONTEND_PATH.set(prefix)
        with AppHarness.create(
            root=tmp_path_factory.mktemp("frontend_path_app"),
            app_source=OnLoadRedirectApp,
        ) as harness:
            assert harness.app_instance is not None, "app is not running"
            environment.REFLEX_FRONTEND_PATH.set("")
            yield harness
    finally:
        environment.REFLEX_FRONTEND_PATH.set("")


@pytest.mark.parametrize(
    ("app_fixture_name", "prefix"),
    [
        ("onload_redirect_app", ""),
        pytest.param(
            "onload_redirect_with_prefix_app",
            "/prefix",
            marks=pytest.mark.xfail(reason="bug #5674"),
        ),
    ],
)
def test_onload_redirect(app_fixture_name: str, prefix: str, page: Page, request):
    app_fixture = request.getfixturevalue(app_fixture_name)
    assert app_fixture.frontend_url is not None

    base_url = app_fixture.frontend_url.rstrip("/")
    base_url += prefix
    page.goto(f"{base_url}/")
    expect(page.get_by_text("This is the index page!")).to_be_visible()

    # Go to /subpage
    page.get_by_text("Go to Subpage!").click()
    expect(page.get_by_text("This is the sub page!")).to_be_visible()

    # Click "Bounce to index!" (should redirect to index via on_load)
    page.get_by_text("Bounce to index!").click()
    expect(page.get_by_text("This is the index page!")).to_be_visible()

    # Optionally, reload /prefix/bouncer/ and check redirect
    page.goto(f"{base_url}/bouncer/")
    expect(page.get_by_text("This is the index page!")).to_be_visible()
