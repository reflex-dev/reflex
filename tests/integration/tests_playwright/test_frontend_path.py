from collections.abc import Generator
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

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
                rx.button("Bounce to index on_load!", on_click=rx.redirect("/bouncer")),
                rx.button(
                    "Bounce to index on_mount!", on_click=rx.redirect("/bouncer-mount")
                ),
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

    @rx.page("/bouncer-mount")
    def bouncer_mount():
        return rx.container(
            rx.vstack(
                rx.heading("This is the bouncer page!"),
                rx.text("You should not be here!"),
                rx.spinner("Go to index!", on_mount=rx.redirect("/")),
            ),
        )

    app = rx.App()  # noqa: F841


@pytest.fixture
def onload_redirect_app(tmp_path: Path) -> Generator[AppHarness, None, None]:
    """Start the OnLoadRedirectApp in prod mode without a frontend_path.

    Baseline to show on_load redirects work without a frontend_path.

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
def onload_redirect_with_prefix_app_dev(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[AppHarness, None, None]:
    """Start the OnLoadRedirectApp in dev mode with frontend_path set to /prefix.

    Args:
        tmp_path: pytest tmp_path fixture
        monkeypatch: pytest monkeypatch fixture to set env var

    Yields:
        running AppHarness instance
    """
    # Set via env var rather than Config directly because AppHarness._initialize_app
    # calls get_config(reload=True), which resets any prior Config mutations.
    monkeypatch.setenv("REFLEX_FRONTEND_PATH", "/prefix")
    with AppHarness.create(
        root=tmp_path / "onload_redirect_with_prefix_app_dev",
        app_source=OnLoadRedirectApp,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


@pytest.fixture
def onload_redirect_with_prefix_app_prod(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[AppHarness, None, None]:
    """Start the OnLoadRedirectApp in prod mode with frontend_path set to /prefix.

    Args:
        tmp_path: pytest tmp_path fixture
        monkeypatch: pytest monkeypatch fixture to set env var

    Yields:
        running AppHarness instance
    """
    monkeypatch.setenv("REFLEX_FRONTEND_PATH", "/prefix")
    with AppHarnessProd.create(
        root=tmp_path / "onload_redirect_with_prefix_app_prod",
        app_source=OnLoadRedirectApp,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


@pytest.mark.ignore_console_error
@pytest.mark.parametrize(
    ("app_fixture_name", "frontend_path"),
    [
        ("onload_redirect_app", ""),
        ("onload_redirect_with_prefix_app_dev", "/prefix"),
        ("onload_redirect_with_prefix_app_prod", "/prefix"),
    ],
)
@pytest.mark.parametrize("redirect_type", ["on_load", "on_mount"])
def test_redirection_triggers(
    app_fixture_name: str,
    frontend_path: str,
    redirect_type: str,
    page: Page,
    request: pytest.FixtureRequest,
):
    """Ensure that on_load and on_mount redirects work with/without a frontend_path.

    Tests both dev mode (AppHarness) and prod mode (AppHarnessProd) to cover
    the bug reported in https://github.com/reflex-dev/reflex/issues/5674,
    where redirects from on_load and on_mount handlers were lost when serving
    from a non-root frontend path.

    Args:
        app_fixture_name: Name of the app fixture to use for the test.
        frontend_path: The frontend_path used by the app fixture.
        redirect_type: Whether to test on_load or on_mount redirection.
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

    # Click "Bounce to index!" (should redirect to index via on_load/on_mount)
    page.get_by_role("button", name=f"Bounce to index {redirect_type}!").click()
    expect(page.get_by_text("This is the index page!")).to_be_visible()
    expect(page).to_have_url(f"{base_url}/")

    # Directly navigate to /bouncer/ and verify redirect
    if redirect_type == "on_mount":
        page.goto(f"{base_url}/bouncer-mount/")
    else:
        page.goto(f"{base_url}/bouncer/")
    expect(page.get_by_text("This is the index page!")).to_be_visible()

    # Check that 404's work and do not change the url
    page.goto(f"{base_url}/not-a-page")
    expect(page.get_by_text("404: Page not found")).to_be_visible()
    expect(page).to_have_url(f"{base_url}/not-a-page")
