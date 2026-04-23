from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def LinkApp():
    import reflex as rx

    app = rx.App()

    def index():
        return rx.vstack(
            rx.box(height="10em"),  # spacer, so the link isn't hovered initially
            rx.link(
                "Click me",
                href="#",
                color="blue",
                _hover=rx.Style({"color": "red"}),
            ),
        )

    app.add_page(index, "/")


@pytest.fixture
def link_app(tmp_path_factory) -> Generator[AppHarness, None, None]:
    with AppHarness.create(
        root=tmp_path_factory.mktemp("link_app"),
        app_source=LinkApp,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


def test_link_hover(link_app: AppHarness, page: Page):
    assert link_app.frontend_url is not None
    page.goto(link_app.frontend_url)

    link = page.get_by_role("link")
    expect(link).to_have_text("Click me")
    expect(link).to_have_css("color", "rgb(0, 0, 255)")
    link.hover()
    expect(link).to_have_css("color", "rgb(255, 0, 0)")
