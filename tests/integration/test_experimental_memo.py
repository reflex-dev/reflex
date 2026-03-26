"""Integration tests for rx._x.memo."""

from collections.abc import Generator

import pytest
from selenium.webdriver.common.by import By

from reflex.testing import AppHarness


def ExperimentalMemoApp():
    """Reflex app that exercises experimental memo functions and components."""
    import reflex as rx

    class FooComponent(rx.Fragment):
        def add_custom_code(self) -> list[str]:
            return [
                "const foo = 'bar'",
            ]

    @rx._x.memo
    def foo_component(label: rx.Var[str]) -> rx.Component:
        return FooComponent.create(label, rx.Var("foo"))

    @rx._x.memo
    def format_price(amount: rx.Var[int], currency: rx.Var[str]) -> rx.Var[str]:
        return currency.to(str) + ": $" + amount.to(str)

    @rx._x.memo
    def summary_card(
        children: rx.Var[rx.Component],
        rest: rx.RestProp,
        *,
        title: rx.Var[str],
        value: rx.Var[str],
    ) -> rx.Component:
        return rx.box(
            rx.heading(title, id="summary-title"),
            rx.text(value, id="summary-value"),
            children,
            rest,
        )

    class ExperimentalMemoState(rx.State):
        amount: int = 125
        currency: str = "USD"
        title: str = "Current Price"

        @rx.event
        def increment_amount(self):
            self.amount += 5

    def index() -> rx.Component:
        formatted_price = format_price(
            amount=ExperimentalMemoState.amount,
            currency=ExperimentalMemoState.currency,
        )
        return rx.vstack(
            rx.vstack(
                foo_component(label="foo"),
                foo_component(label="bar"),
                id="experimental-memo-custom-code",
            ),
            rx.text(formatted_price, id="formatted-price"),
            rx.button(
                "Increment",
                id="increment-price",
                on_click=ExperimentalMemoState.increment_amount,
            ),
            summary_card(
                rx.text("Children are passed positionally.", id="summary-child"),
                title=ExperimentalMemoState.title,
                value=formatted_price,
                id="summary-card",
                class_name="forwarded-summary-card",
            ),
        )

    app = rx.App()
    app.add_page(index)


@pytest.fixture
def experimental_memo_app(tmp_path) -> Generator[AppHarness, None, None]:
    """Start ExperimentalMemoApp app at tmp_path via AppHarness.

    Args:
        tmp_path: pytest tmp_path fixture.

    Yields:
        Running AppHarness instance.
    """
    with AppHarness.create(
        root=tmp_path,
        app_source=ExperimentalMemoApp,
    ) as harness:
        yield harness


def test_experimental_memo_app(experimental_memo_app: AppHarness):
    """Render experimental memos and assert on their frontend behavior.

    Args:
        experimental_memo_app: Harness for ExperimentalMemoApp.
    """
    assert experimental_memo_app.app_instance is not None, "app is not running"
    driver = experimental_memo_app.frontend()

    memo_custom_code_stack = AppHarness.poll_for_or_raise_timeout(
        lambda: driver.find_element(By.ID, "experimental-memo-custom-code")
    )
    assert (
        experimental_memo_app.poll_for_content(memo_custom_code_stack, exp_not_equal="")
        == "foobarbarbar"
    )
    assert memo_custom_code_stack.text == "foobarbarbar"

    formatted_price = driver.find_element(By.ID, "formatted-price")
    assert (
        experimental_memo_app.poll_for_content(formatted_price, exp_not_equal="")
        == "USD: $125"
    )

    summary_card = driver.find_element(By.ID, "summary-card")
    assert "forwarded-summary-card" in (summary_card.get_attribute("class") or "")
    assert driver.find_element(By.ID, "summary-title").text == "Current Price"
    assert (
        driver.find_element(By.ID, "summary-child").text
        == "Children are passed positionally."
    )

    summary_value = driver.find_element(By.ID, "summary-value")
    assert (
        experimental_memo_app.poll_for_content(summary_value, exp_not_equal="")
        == "USD: $125"
    )

    driver.find_element(By.ID, "increment-price").click()
    assert experimental_memo_app.poll_for_content(formatted_price) == "USD: $130"
    assert experimental_memo_app.poll_for_content(summary_value) == "USD: $130"
