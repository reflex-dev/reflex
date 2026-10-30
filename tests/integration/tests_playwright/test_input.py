"""Integration tests for text input and related components."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def FullyControlledInput():
    """App using a fully controlled input with implicit debounce wrapper."""
    import reflex as rx

    class State(rx.State):
        text: str = "initial"

        @rx.event
        def set_text(self, text: str):
            self.text = text

        @rx.event
        def do_clear(self):
            self.text = ""

    app = rx.App()

    @app.add_page
    def index():
        return rx.fragment(
            rx.input(
                value=State.router.session.client_token, is_read_only=True, id="token"
            ),
            rx.button(
                "Clear State",
                on_click=State.do_clear,
                id="clear-backend",
            ),
            rx.input(
                id="debounce_input_input",
                on_change=State.set_text,
                value=State.text,
            ),
            rx.input(value=State.text, id="value_input", is_read_only=True),
            rx.input(on_change=State.set_text, id="on_change_input"),
            rx.el.input(
                value=State.text,
                id="plain_value_input",
                disabled=True,
                _disabled={"width": "42px"},
            ),
            rx.input(default_value="default", id="default_input"),
            rx.el.input(
                type="text", default_value="default plain", id="plain_default_input"
            ),
            rx.checkbox(default_checked=True, id="default_checkbox"),
            rx.el.input(
                type="checkbox", default_checked=True, id="plain_default_checkbox"
            ),
            rx.button(
                "CLEAR", on_click=rx.set_value("on_change_input", ""), id="clear"
            ),
        )


@pytest.fixture
def fully_controlled_input(tmp_path) -> Generator[AppHarness, None, None]:
    """Start the controlled-input app.

    Yields:
        The running app harness.
    """
    with AppHarness.create(
        root=tmp_path,
        app_source=FullyControlledInput,
    ) as harness:
        yield harness


def test_fully_controlled_input(fully_controlled_input: AppHarness, page: Page):
    """Input edits and backend state changes stay synchronized in the browser."""
    assert fully_controlled_input.app_instance is not None, "app is not running"
    assert fully_controlled_input.frontend_url is not None
    page.goto(fully_controlled_input.frontend_url)

    expect(page.locator("#token")).not_to_have_value("")
    expect(page.locator("#default_input")).to_have_value("default")
    expect(page.locator("#plain_default_input")).to_have_value("default plain")
    expect(page.locator("#default_checkbox")).to_be_checked()
    expect(page.locator("#plain_default_checkbox")).to_be_checked()

    debounce_input = page.locator("#debounce_input_input")
    value_input = page.locator("#value_input")
    on_change_input = page.locator("#on_change_input")
    plain_value_input = page.locator("#plain_value_input")

    expect(debounce_input).to_have_value("initial")
    expect(value_input).to_have_value("initial")
    expect(plain_value_input).to_have_value("initial")
    expect(plain_value_input).to_have_css("width", "42px")

    debounce_input.press("Home")
    debounce_input.press("ArrowRight")
    debounce_input.type("foo")
    expect(debounce_input).to_have_value("ifoonitial")
    expect(value_input).to_have_value("ifoonitial")
    expect(plain_value_input).to_have_value("ifoonitial")

    page.locator("#clear-backend").click()
    expect(debounce_input).to_have_value("")
    expect(value_input).to_have_value("")
    expect(plain_value_input).to_have_value("")

    debounce_input.fill("getting testing done")
    expect(debounce_input).to_have_value("getting testing done")
    expect(value_input).to_have_value("getting testing done")
    expect(plain_value_input).to_have_value("getting testing done")

    on_change_input.fill("overwrite the state")
    expect(debounce_input).to_have_value("overwrite the state")
    expect(on_change_input).to_have_value("overwrite the state")
    expect(value_input).to_have_value("overwrite the state")
    expect(plain_value_input).to_have_value("overwrite the state")

    page.locator("#clear").click()
    expect(on_change_input).to_have_value("")
