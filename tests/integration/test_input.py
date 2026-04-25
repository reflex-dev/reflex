"""Integration tests for text input and related components."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness

from . import utils


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


@pytest.fixture(scope="module")
def fully_controlled_input(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start FullyControlledInput app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("fully_controlled_input"),
        app_source=FullyControlledInput,
    ) as harness:
        yield harness


def test_fully_controlled_input(fully_controlled_input: AppHarness, page: Page):
    """Type text after moving cursor. Update text on backend.

    Args:
        fully_controlled_input: harness for FullyControlledInput app
        page: Playwright page.
    """
    assert fully_controlled_input.frontend_url is not None
    page.goto(fully_controlled_input.frontend_url)

    # wait for the backend connection to send the token
    utils.poll_for_token(page)

    # ensure defaults are set correctly
    expect(page.locator("#default_input")).to_have_value("default")
    expect(page.locator("#plain_default_input")).to_have_value("default plain")
    expect(page.locator("#default_checkbox")).to_have_value("on")
    expect(page.locator("#plain_default_checkbox")).to_have_value("on")

    # find the input and wait for it to have the initial state value
    debounce_input = page.locator("#debounce_input_input")
    value_input = page.locator("#value_input")
    on_change_input = page.locator("#on_change_input")
    plain_value_input = page.locator("#plain_value_input")
    clear_button = page.locator("#clear")
    expect(debounce_input).to_have_value("initial")
    expect(value_input).to_have_value("initial")
    expect(plain_value_input).to_have_value("initial")
    expect(plain_value_input).to_have_css("width", "42px")

    # move cursor to home, then to the right and type characters
    debounce_input.click()
    for _ in range(len("initial")):
        page.keyboard.press("ArrowLeft")
    page.keyboard.press("ArrowRight")
    page.keyboard.type("foo")
    expect(value_input).to_have_value("ifoonitial")
    expect(debounce_input).to_have_value("ifoonitial")
    expect(plain_value_input).to_have_value("ifoonitial")

    # clear the input on the backend
    page.locator("#clear-backend").click()
    expect(debounce_input).to_have_value("")

    # type more characters
    debounce_input.click()
    debounce_input.press_sequentially("getting testing done")
    expect(value_input).to_have_value("getting testing done")
    expect(debounce_input).to_have_value("getting testing done")
    expect(plain_value_input).to_have_value("getting testing done")

    # type into the on_change input
    on_change_input.click()
    on_change_input.press_sequentially("overwrite the state")
    expect(value_input).to_have_value("overwrite the state")
    expect(debounce_input).to_have_value("overwrite the state")
    expect(on_change_input).to_have_value("overwrite the state")
    expect(plain_value_input).to_have_value("overwrite the state")

    clear_button.click()
    expect(on_change_input).to_have_value("")
    # potential bug: clearing the on_change field doesn't itself trigger on_change
    # assert backend_state.text == "" #noqa: ERA001
    # assert debounce_input.get_attribute("value") == "" #noqa: ERA001
    # assert value_input.get_attribute("value") == "" #noqa: ERA001
