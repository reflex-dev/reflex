from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.environment import environment
from reflex.testing import AppHarness, AppHarnessProd


def OnLoadRedirectApp():
    """App to demonstrate an on_load redirection issue.

    See https://github.com/reflex-dev/reflex/issues/5674 for details.
    """
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
def onload_redirect_app(tmp_path) -> Generator[AppHarness, None, None]:
    """Start the OnLoadRedirectApp without setting REFLEX_FRONTEND_PATH".

    This is a baseline used to show on_load redirects work without a frontend_path.

    Args:
        tmp_path: pytest tmp_path fixture

    Yields:
        running AppHarness instance
    """
    with AppHarnessProd.create(
        root=tmp_path / "onload_redirect_app",
        app_source=OnLoadRedirectApp,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


@pytest.fixture
def onload_redirect_with_prefix_app(tmp_path) -> Generator[AppHarness, None, None]:
    """Start the OnLoadRedirectApp with REFLEX_FRONTEND_PATH set to "/prefix".

    This simulates setting the REFLEX_FRONTEND_PATH to identify issues with redirection.

    Args:
        tmp_path: pytest tmp_path fixture

    Yields:
        running AppHarness instance
    """
    prefix = "/prefix"
    try:
        environment.REFLEX_FRONTEND_PATH.set(prefix)
        with AppHarness.create(
            root=tmp_path / "onload_redirect_with_prefix_app",
            app_source=OnLoadRedirectApp,
        ) as harness:
            assert harness.app_instance is not None, "app is not running"
            environment.REFLEX_FRONTEND_PATH.set("")
            yield harness
    finally:
        environment.REFLEX_FRONTEND_PATH.set("")


def OnMountRedirectApp():
    """App demonstrate on_mount redirection behaviour."""
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

    @rx.page("/bouncer")
    def bouncer():
        return rx.container(
            rx.vstack(
                rx.heading("This is the bouncer page!"),
                rx.text("You should not be here!"),
                rx.spinner("Go to index!", on_mount=rx.redirect("/")),
            ),
        )

    app = rx.App()  # noqa: F841


@pytest.fixture
def onmount_redirect_app(tmp_path) -> Generator[AppHarness, None, None]:
    """Start the OnMountRedirectApp without setting REFLEX_FRONTEND_PATH".

    This is a baseline used to show on_mount redirects work without a frontend_path.

    Args:
        tmp_path: pytest tmp_path fixture

    Yields:
        running AppHarness instance
    """
    with AppHarnessProd.create(
        root=tmp_path / "onmount_redirect_app",
        app_source=OnMountRedirectApp,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


@pytest.fixture
def onmount_redirect_with_prefix_app(tmp_path) -> Generator[AppHarness, None, None]:
    """Start the OnMountRedirectApp with REFLEX_FRONTEND_PATH set to "/prefix".

    This simulates setting the REFLEX_FRONTEND_PATH to identify issues with redirection.

    Args:
        tmp_path: pytest tmp_path fixture

    Yields:
        running AppHarness instance
    """
    prefix = "/prefix"
    try:
        environment.REFLEX_FRONTEND_PATH.set(prefix)
        with AppHarness.create(
            root=tmp_path / "onmount_redirect_with_prefix_app",
            app_source=OnMountRedirectApp,
        ) as harness:
            assert harness.app_instance is not None, "app is not running"
            environment.REFLEX_FRONTEND_PATH.set("")
            yield harness
    finally:
        environment.REFLEX_FRONTEND_PATH.set("")


@pytest.mark.parametrize(
    ("app_fixture_name", "frontend_path"),
    [
        ("onload_redirect_app", ""),
        ("onload_redirect_with_prefix_app", "/prefix"),
        ("onmount_redirect_app", ""),
        ("onmount_redirect_with_prefix_app", "/prefix"),
    ],
)
def test_redirection_triggers(
    app_fixture_name: str, frontend_path: str, page: Page, request
):
    """Ensure that on_load and on_mount redirects work with/without a frontend_path.

    Args:
        app_fixture_name: Name of the app fixture to use for the test.
        frontend_path: The REFLEX_FRONTEND_PATH used by the app fixture.
        page: Playwright Page object to interact with the app.
        request: Pytest request object to access fixtures.
    """
    app_fixture = request.getfixturevalue(app_fixture_name)
    assert app_fixture.frontend_url is not None

    base_url = app_fixture.frontend_url.rstrip("/")
    base_url += frontend_path
    page.goto(f"{base_url}/")
    expect(page.get_by_text("This is the index page!")).to_be_visible()

    # Go to /subpage
    page.get_by_role("button", name="Go to Subpage!").click()
    expect(page.get_by_text("This is the sub page!")).to_be_visible()
    expect(page).to_have_url(f"{base_url}/subpage")

    # Click "Bounce to index!" (should redirect to index via on_load)
    page.get_by_role("button", name="Bounce to index!").click()
    expect(page.get_by_text("This is the index page!")).to_be_visible()
    expect(page).to_have_url(f"{base_url}/")

    # Optionally, reload /prefix/bouncer/ and check redirect
    page.goto(f"{base_url}/bouncer/")
    expect(page.get_by_text("This is the index page!")).to_be_visible()

    # Check that 404's work and do not change the url
    page.goto(f"{base_url}/not-a-page")
    expect(page.get_by_text("404: Page not found")).to_be_visible()
    expect(page).to_have_url(f"{base_url}/not-a-page")
