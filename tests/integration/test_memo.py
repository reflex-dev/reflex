"""Integration tests for rx.memo components."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def MemoApp():
    """Reflex app with memo components."""
    import reflex as rx

    class FooComponent(rx.Fragment):
        def add_custom_code(self) -> list[str]:
            return [
                "const foo = 'bar'",
            ]

    @rx.memo
    def foo_component(t: str):
        return FooComponent.create(t, rx.Var("foo"))

    @rx.memo
    def foo_component2(t: str):
        return FooComponent.create(t, rx.Var("foo"))

    class MemoState(rx.State):
        last_value: str = ""

        @rx.event
        def set_last_value(self, value: str):
            self.last_value = value

    @rx.memo
    def my_memoed_component(
        some_value: str,
        event: rx.EventHandler[rx.event.passthrough_event_spec(str)],
    ) -> rx.Component:
        return rx.vstack(
            rx.button(some_value, id="memo-button", on_click=event(some_value)),
            rx.input(id="memo-input", on_change=event),
        )

    def index() -> rx.Component:
        return rx.vstack(
            rx.vstack(
                foo_component(t="foo"), foo_component2(t="bar"), id="memo-custom-code"
            ),
            rx.text(MemoState.last_value, id="memo-last-value"),
            my_memoed_component(
                some_value="memod_some_value", event=MemoState.set_last_value
            ),
        )

    app = rx.App()
    app.add_page(index)


@pytest.fixture(scope="module")
def memo_app(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start MemoApp app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("memo_app"),
        app_source=MemoApp,
    ) as harness:
        yield harness


def test_memo_app(memo_app: AppHarness, page: Page):
    """Render various memo'd components and assert on the output.

    Args:
        memo_app: harness for MemoApp app
        page: Playwright Page fixture
    """
    assert memo_app.app_instance is not None, "app is not running"
    assert memo_app.frontend_url is not None
    page.goto(memo_app.frontend_url)

    # check that the output matches
    memo_custom_code_stack = page.locator("#memo-custom-code")
    expect(memo_custom_code_stack).to_have_text("foobarbarbar")

    # click the button to trigger partial event application
    page.locator("#memo-button").click()
    last_value = page.locator("#memo-last-value")
    expect(last_value).to_have_text("memod_some_value")

    # enter text to trigger passed argument to event handler
    page.locator("#memo-input").fill("new_value")
    expect(last_value).to_have_text("new_value")
