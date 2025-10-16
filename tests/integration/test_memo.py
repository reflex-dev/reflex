"""Integration tests for rx.memo components."""

from collections.abc import Generator

import pytest
from selenium.webdriver.common.by import By

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


@pytest.fixture
def memo_app(tmp_path) -> Generator[AppHarness, None, None]:
    """Start MemoApp app at tmp_path via AppHarness.

    Args:
        tmp_path: pytest tmp_path fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path,
        app_source=MemoApp,
    ) as harness:
        yield harness


def test_memo_app(memo_app: AppHarness):
    """Render various memo'd components and assert on the output.

    Args:
        memo_app: harness for MemoApp app
    """
    assert memo_app.app_instance is not None, "app is not running"
    driver = memo_app.frontend()

    # check that the output matches
    memo_custom_code_stack = AppHarness.poll_for_or_raise_timeout(
        lambda: driver.find_element(By.ID, "memo-custom-code")
    )
    assert (
        memo_app.poll_for_content(memo_custom_code_stack, exp_not_equal="")
        == "foobarbarbar"
    )
    assert memo_custom_code_stack.text == "foobarbarbar"

    # click the button to trigger partial event application
    button = driver.find_element(By.ID, "memo-button")
    button.click()
    last_value = driver.find_element(By.ID, "memo-last-value")
    assert memo_app.poll_for_content(last_value, exp_not_equal="") == "memod_some_value"

    # enter text to trigger passed argument to event handler
    textbox = driver.find_element(By.ID, "memo-input")
    textbox.send_keys("new_value")
    AppHarness.expect(lambda: memo_app.poll_for_content(last_value) == "new_value")
