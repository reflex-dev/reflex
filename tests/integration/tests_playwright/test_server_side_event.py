"""Integration tests for special server-side events."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


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
    """Start the server-side event app.

    Yields:
        The running app harness.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("server_side_event"),
        app_source=ServerSideEvent,
    ) as harness:
        yield harness


@pytest.fixture(autouse=True)
def open_server_side_event(server_side_event: AppHarness, page: Page) -> None:
    """Open the app and wait for its backend connection."""
    assert server_side_event.app_instance is not None, "app is not running"
    assert server_side_event.frontend_url is not None
    page.goto(server_side_event.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")


@pytest.mark.parametrize(
    "button_id",
    [
        "clear_immediate",
        "clear_chained_yield",
        "clear_chained_yield_return",
        "clear_chained_return",
    ],
)
def test_set_value(button_id: str, page: Page) -> None:
    """Each event-chain form clears all three input values."""
    inputs = [page.locator(f"#{field}") for field in ("a", "b", "c")]
    for field, value in zip(inputs, ("a", "b", "c"), strict=True):
        expect(field).to_have_value(value)

    page.locator(f"#{button_id}").click()
    for field in inputs:
        expect(field).to_have_value("")


def test_set_value_return_c(page: Page) -> None:
    """Returning one set_value event changes only its target input."""
    inputs = [page.locator(f"#{field}") for field in ("a", "b", "c")]
    page.locator("#clear_return_c").click()

    expect(inputs[0]).to_have_value("a")
    expect(inputs[1]).to_have_value("b")
    expect(inputs[2]).to_have_value("")


def test_set_focus(page: Page) -> None:
    """The set_focus event focuses its target input."""
    page.locator("#focus_input").click()
    expect(page.locator("#focus_target")).to_be_focused()
