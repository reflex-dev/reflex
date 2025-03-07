"""Integration tests for rx.memo components."""

from typing import Generator

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

    def index() -> rx.Component:
        return rx.vstack(
            foo_component(t="foo"), foo_component2(t="bar"), id="memo-custom-code"
        )

    app = rx.App()
    app.add_page(index)


@pytest.fixture()
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


@pytest.mark.asyncio
async def test_memo_app(memo_app: AppHarness):
    """Render various memo'd components and assert on the output.

    Args:
        memo_app: harness for MemoApp app
    """
    assert memo_app.app_instance is not None, "app is not running"
    driver = memo_app.frontend()

    # check that the output matches
    memo_custom_code_stack = driver.find_element(By.ID, "memo-custom-code")
    assert memo_custom_code_stack.text == "foobarbarbar"
