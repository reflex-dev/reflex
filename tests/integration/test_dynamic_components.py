"""Integration tests for var operations."""

from collections.abc import Generator
from typing import TypeVar

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness

from . import utils

# pyright: reportOptionalMemberAccess=false, reportGeneralTypeIssues=false, reportUnknownMemberType=false


def DynamicComponents():
    """App with var operations."""
    import reflex as rx

    class DynamicComponentsState(rx.State):
        value: int = 10

        button: rx.Component = rx.button(
            "Click me",
            custom_attrs={
                "id": "button",
            },
        )

        @rx.event
        def got_clicked(self):
            self.button = rx.button(
                "Clicked",
                custom_attrs={
                    "id": "button",
                },
            )

        @rx.var
        def client_token_component(self) -> rx.Component:
            return rx.vstack(
                rx.el.input(
                    custom_attrs={
                        "id": "token",
                    },
                    value=self.router.session.client_token,
                    is_read_only=True,
                ),
                rx.button(
                    "Update",
                    custom_attrs={
                        "id": "update",
                    },
                    on_click=DynamicComponentsState.got_clicked,
                ),
            )

    app = rx.App()

    def factorial(n: int) -> int:
        if n == 0:
            return 1
        return n * factorial(n - 1)

    @app.add_page
    def index():
        return rx.vstack(
            DynamicComponentsState.client_token_component,
            DynamicComponentsState.button,
            rx.text(
                DynamicComponentsState._evaluate(
                    lambda state: factorial(state.value), of_type=int
                ),
                id="factorial",
            ),
        )


@pytest.fixture(scope="module")
def dynamic_components(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start VarOperations app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("dynamic_components"),
        app_source=DynamicComponents,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


T = TypeVar("T")


def test_dynamic_components(page: Page, dynamic_components: AppHarness):
    """Test that the var operations produce the right results.

    Args:
        page: Playwright page.
        dynamic_components: AppHarness for the dynamic components
    """
    assert dynamic_components.frontend_url is not None
    page.goto(dynamic_components.frontend_url)

    utils.poll_for_token(page)

    button = page.locator("#button")
    expect(button).to_have_text("Click me")

    update_button = page.locator("#update")
    expect(update_button).to_be_visible()
    update_button.click()

    expect(button).to_have_text("Clicked")

    factorial = page.locator("#factorial")
    expect(factorial).to_have_text("3628800")
