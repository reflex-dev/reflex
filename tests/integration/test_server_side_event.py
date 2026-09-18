"""Integration tests for special server side events."""

import time
from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness

from . import utils


def ServerSideEvent():
    """App with inputs set via event handlers and set_value."""
    import reflex as rx

    class SSState(rx.State):
        @rx.event
        def set_value_yield(self):
            yield rx.set_value("a", "")
            yield rx.set_value("b", "")
            yield rx.set_value("c", "")

        @rx.event
        def set_value_yield_return(self):
            yield rx.set_value("a", "")
            yield rx.set_value("b", "")
            return rx.set_value("c", "")  # noqa: B901

        @rx.event
        def set_value_return(self):
            return [
                rx.set_value("a", ""),
                rx.set_value("b", ""),
                rx.set_value("c", ""),
            ]

        @rx.event
        def set_value_return_c(self):
            return rx.set_value("c", "")

    app = rx.App()

    @app.add_page
    def index():
        return rx.fragment(
            rx.input(
                id="token", value=SSState.router.session.client_token, is_read_only=True
            ),
            rx.input(default_value="a", id="a"),
            rx.input(default_value="b", id="b"),
            rx.input(default_value="c", id="c"),
            rx.el.input(name="name", id="focus_target"),
            rx.button(
                "Clear Immediate",
                id="clear_immediate",
                on_click=[
                    rx.set_value("a", ""),
                    rx.set_value("b", ""),
                    rx.set_value("c", ""),
                ],
            ),
            rx.button(
                "Clear Chained Yield",
                id="clear_chained_yield",
                on_click=SSState.set_value_yield,
            ),
            rx.button(
                "Clear Chained Yield+Return",
                id="clear_chained_yield_return",
                on_click=SSState.set_value_yield_return,
            ),
            rx.button(
                "Clear Chained Return",
                id="clear_chained_return",
                on_click=SSState.set_value_return,
            ),
            rx.button(
                "Clear C Return",
                id="clear_return_c",
                on_click=SSState.set_value_return_c,
            ),
            rx.el.button(
                "Focus input",
                id="focus_input",
                on_click=rx.set_focus("focus_target"),
            ),
        )


@pytest.fixture(scope="module")
def server_side_event(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start ServerSideEvent app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("server_side_event"),
        app_source=ServerSideEvent,
    ) as harness:
        yield harness


@pytest.mark.parametrize(
    "button_id",
    [
        "clear_immediate",
        "clear_chained_yield",
        "clear_chained_yield_return",
        "clear_chained_return",
    ],
)
def test_set_value(server_side_event: AppHarness, page: Page, button_id: str):
    """Call set_value as an event chain, via yielding, via yielding with return.

    Args:
        server_side_event: harness for ServerSideEvent app
        page: Playwright page.
        button_id: id of the button to click (parametrized)
    """
    assert server_side_event.frontend_url is not None
    page.goto(server_side_event.frontend_url)

    utils.poll_for_token(page)

    input_a = page.locator("#a")
    input_b = page.locator("#b")
    input_c = page.locator("#c")
    btn = page.locator(f"#{button_id}")

    expect(input_a).to_have_value("a")
    expect(input_b).to_have_value("b")
    expect(input_c).to_have_value("c")
    btn.click()
    time.sleep(0.2)
    expect(input_a).to_have_value("")
    expect(input_b).to_have_value("")
    expect(input_c).to_have_value("")


def test_set_value_return_c(server_side_event: AppHarness, page: Page):
    """Call set_value returning single event.

    Args:
        server_side_event: harness for ServerSideEvent app
        page: Playwright page.
    """
    assert server_side_event.frontend_url is not None
    page.goto(server_side_event.frontend_url)

    utils.poll_for_token(page)

    input_a = page.locator("#a")
    input_b = page.locator("#b")
    input_c = page.locator("#c")
    btn = page.locator("#clear_return_c")

    expect(input_a).to_have_value("a")
    expect(input_b).to_have_value("b")
    expect(input_c).to_have_value("c")
    btn.click()
    time.sleep(0.2)
    expect(input_a).to_have_value("a")
    expect(input_b).to_have_value("b")
    expect(input_c).to_have_value("")


def test_set_focus(server_side_event: AppHarness, page: Page):
    """Call set_focus and verify the target input becomes active.

    Args:
        server_side_event: harness for ServerSideEvent app
        page: Playwright page.
    """
    assert server_side_event.frontend_url is not None
    page.goto(server_side_event.frontend_url)

    utils.poll_for_token(page)

    input_target = page.locator("#focus_target")
    btn = page.locator("#focus_input")

    expect(input_target).to_be_visible()
    expect(btn).to_be_visible()

    btn.click()

    expect(input_target).to_be_focused()
