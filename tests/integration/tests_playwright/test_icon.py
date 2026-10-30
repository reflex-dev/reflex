"""Integration tests for the Icon component."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect
from reflex_components_lucide.icon import LUCIDE_ICON_LIST

from reflex.testing import AppHarness


def Icons():
    from reflex_components_lucide.icon import LUCIDE_ICON_LIST

    import reflex as rx

    app = rx.App()

    class State(rx.State):
        """State for the Icons app."""

        dynamic_icon: str = "airplay"

    @app.add_page
    def index():
        return rx.vstack(
            rx.el.input(
                custom_attrs={"id": "token"},
                value=State.router.session.client_token,
                is_read_only=True,
            ),
            rx.el.div(
                rx.icon(State.dynamic_icon),
                id="dynamic_icon",
            ),
            *[
                rx.el.div(rx.icon(icon_name), id=icon_name)
                for icon_name in LUCIDE_ICON_LIST
            ],
        )


@pytest.fixture(scope="module")
def icons(
    tmp_path_factory, app_harness_env: type[AppHarness]
) -> Generator[AppHarness, None, None]:
    """Start the icon app with the selected harness mode.

    Yields:
        The running app harness.
    """
    with app_harness_env.create(
        root=tmp_path_factory.mktemp("icons"),
        app_source=Icons,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


def test_icons(icons: AppHarness, page: Page) -> None:
    """All static and state-driven icons render as SVGs."""
    assert icons.frontend_url is not None
    page.goto(icons.frontend_url)
    expect(page.locator("#token")).not_to_have_value("", timeout=30_000)

    for icon_name in [*LUCIDE_ICON_LIST, "dynamic_icon"]:
        expect(page.locator(f'[id="{icon_name}"] svg')).to_have_count(1)
